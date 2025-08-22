const form = document.getElementById('askForm');
const input = document.getElementById('question');
const messages = document.getElementById('messages');
const btn = document.getElementById('sendBtn');
const voiceBtn = document.getElementById('voiceBtn');
const pdfInput = document.getElementById('pdfUpload');

// Voice recognition using Web Speech API
if (voiceBtn && (window.SpeechRecognition || window.webkitSpeechRecognition)) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  let listeningMsg = null;

  voiceBtn.addEventListener('click', () => {
    input.value = '';
    recognition.start();
    voiceBtn.disabled = true;
    voiceBtn.textContent = 'Listening...';
    listeningMsg = addMessage('user', '[Listening...]');
  });

  recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript;
    input.value = transcript;
    voiceBtn.disabled = false;
    voiceBtn.textContent = '🎤';
    if (listeningMsg) {
      listeningMsg.textContent = transcript;
      listeningMsg = null;
    } else {
      addMessage('user', transcript);
    }
    input.disabled = true;
    btn.disabled = true;
    const typing = showTyping();
    try {
      const res = await fetch('/ask', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({question:transcript})
      });
      const data = await res.json();
      typing.stop();
      typing.node.remove();
      addMessage('bot', data.answer || 'No response');
      // Read bot response aloud
      if ('speechSynthesis' in window) {
        const utter = new SpeechSynthesisUtterance(data.answer || 'No response');
        utter.lang = 'en-US';
        window.speechSynthesis.speak(utter);
      }
    } catch (err) {
      typing.stop();
      typing.node.remove();
      addMessage('bot', 'Network error: '+err.message);
      console.error('Voice feature error:', err);
    } finally {
      input.disabled = false;
      btn.disabled = false;
      input.value = '';
      input.focus();
    }
  };
  recognition.onerror = (event) => {
    voiceBtn.disabled = false;
    voiceBtn.textContent = '🎤';
    if (listeningMsg) {
      listeningMsg.textContent = '[Voice error]';
      listeningMsg = null;
    }
    console.error('Speech recognition error:', event.error);
  };
  recognition.onend = () => {
    voiceBtn.disabled = false;
    voiceBtn.textContent = '🎤';
    if (listeningMsg) {
      listeningMsg.textContent = '[Stopped listening]';
      listeningMsg = null;
    }
  };
} else {
  if (voiceBtn) {
    voiceBtn.disabled = true;
    voiceBtn.title = 'Voice feature not supported in this browser.';
    console.warn('SpeechRecognition API not supported in this browser.');
  }
}

function el(tag, cls, text){
  const e = document.createElement(tag);
  if(cls) e.className = cls;
  if(text !== undefined) e.textContent = text;
  return e;
}

// Remove speak function and speech synthesis from addMessage
function addMessage(role, text){
  const bubble = el('div', `msg ${role}`);
  bubble.textContent = text;
  messages.appendChild(bubble);
  messages.scrollTop = messages.scrollHeight;
  return bubble;
}

function showTyping(){
  const dots = el('div', 'msg bot');
  let step = 0;
  const frames = ['…','..','.' ,'..'];
  const id = setInterval(()=>{
    dots.textContent = 'Thinking' + frames[step % frames.length];
    step++;
  }, 300);
  messages.appendChild(dots);
  messages.scrollTop = messages.scrollHeight;
  return {node:dots, stop:()=>clearInterval(id)};
}

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  const q = input.value.trim();
  if(!q) return;
  addMessage('user', q);
  input.value = '';
  input.disabled = true;
  btn.disabled = true;

  const typing = showTyping();
  try{
    const res = await fetch('/ask', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({question:q})
    });
    const data = await res.json();
    typing.stop();
    typing.node.remove();
    const answer = data.answer || 'No response';
    addMessage('bot', answer);
  }catch(err){
    typing.stop();
    typing.node.remove();
    addMessage('bot', 'Network error: '+err.message);
  }finally{
    input.disabled = false;
    btn.disabled = false;
    input.focus();
  }
});

// PDF upload and summarization
if (pdfInput) {
  pdfInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    addMessage('user', `Uploaded PDF: ${file.name}`);
    const formData = new FormData();
    formData.append('pdf', file);
    const typing = showTyping();
    try {
      const res = await fetch('/pdf', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      typing.stop();
      typing.node.remove();
      addMessage('bot', data.summary || 'No summary');
    } catch (err) {
      typing.stop();
      typing.node.remove();
      addMessage('bot', 'PDF error: ' + err.message);
    }
  });
}
