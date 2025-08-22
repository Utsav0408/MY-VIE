from flask import Flask, render_template, request, jsonify, send_file
from dotenv import load_dotenv
import os
import traceback
from datetime import datetime
import tempfile
import PyPDF2
from werkzeug.utils import secure_filename
import sqlite3
from flask import session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash

# Optional text-to-speech fallback
try:
    from gtts import gTTS
    HAVE_GTTS = True
except Exception:
    HAVE_GTTS = False

# Google Generative AI SDK
try:
    import google.generativeai as genai
except Exception:
    genai = None

load_dotenv()
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
app.config['SESSION_TYPE'] = 'filesystem'

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-1.5-flash")

# Configure Gemini
model = None
if not GEMINI_API_KEY:
    print("[Startup] ERROR: GEMINI_API_KEY not found in environment.")
elif not genai:
    print("[Startup] ERROR: google-generativeai SDK not installed.")
else:
    try:
        print(f"[Startup] GEMINI_API_KEY loaded: {GEMINI_API_KEY[:6]}... (hidden)")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel(MODEL_NAME)
    except Exception as e:
        print(f"[Startup] Failed to initialize GenerativeModel: {e}")
        traceback.print_exc()

CONVERSATION = []

def extract_pdf_text(file_stream):
    try:
        reader = PyPDF2.PdfReader(file_stream)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text
    except Exception as e:
        print(f"[PDF] Error extracting text: {e}")
        return ""

@app.route('/')
def index():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

@app.route('/ask', methods=['POST'])
def ask():
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get('question') or "").strip()
        if not question:
            return jsonify({'ok': False, 'answer': "Please ask a valid question."}), 400

        msg = {'role': 'user', 'content': question, 'time': datetime.utcnow().isoformat()}
        CONVERSATION.append(msg)

        if not model:
            return jsonify({'ok': False, 'answer': "Gemini API not configured."}), 503

        try:
            resp = model.generate_content(question)
            response_text = getattr(resp, "text", None) or str(resp)
        except Exception as gen_err:
            print(f"[GenAI] Error: {gen_err}")
            traceback.print_exc()
            response_text = f"Sorry, I hit an error: {gen_err}"

        CONVERSATION.append({'role': 'assistant', 'content': response_text, 'time': datetime.utcnow().isoformat()})
        return jsonify({'ok': True, 'answer': response_text})
    except Exception as e:
        print(f"[/ask] General error: {e}")
        traceback.print_exc()
        return jsonify({'ok': False, 'answer': f"Unexpected server error: {e}"}), 500

@app.route('/pdf', methods=['POST'])
def pdf():
    if not model:
        return jsonify({'ok': False, 'summary': "Gemini API not configured."}), 503
    if 'pdf' not in request.files:
        return jsonify({'ok': False, 'summary': "No PDF uploaded."}), 400

    pdf_file = request.files['pdf']
    filename = secure_filename(pdf_file.filename)
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        pdf_file.save(tmp.name)
        text = extract_pdf_text(tmp.name)

    if not text.strip():
        return jsonify({'ok': False, 'summary': "Could not extract text from PDF."}), 400

    try:
        prompt = f"Summarize this PDF and answer any questions about it:\n{text[:5000]}"
        resp = model.generate_content(prompt)
        summary = getattr(resp, "text", None) or str(resp)
    except Exception as e:
        print(f"[PDF] Gemini error: {e}")
        summary = f"Error summarizing PDF: {e}"

    return jsonify({'ok': True, 'summary': summary})

# --- Voice: backend TTS route ---
@app.route('/tts', methods=['POST'])
def tts():
    data = request.get_json(silent=True) or {}
    text = (data.get('text') or "").strip()
    if not text:
        return jsonify({'ok': False, 'error': 'No text provided.'}), 400
    if not HAVE_GTTS:
        return jsonify({'ok': False, 'error': 'gTTS not installed; use browser speech.'}), 503
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
            gTTS(text).save(tmp.name)
            return send_file(tmp.name, mimetype="audio/mpeg", as_attachment=False)
    except Exception as e:
        print(f"[TTS] Error: {e}")
        return jsonify({'ok': False, 'error': f'TTS error: {e}'}), 500

# User DB helpers
DB_PATH = os.path.join(os.path.dirname(__file__), 'users.db')
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            role TEXT,
            content TEXT,
            time TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )''')
init_db()

# Auth routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.execute('SELECT id, password FROM users WHERE username=?', (username,))
            row = cur.fetchone()
            if row and check_password_hash(row[1], password):
                session['user_id'] = row[0]
                session['username'] = username
                return redirect(url_for('index'))
            else:
                error = 'Invalid username or password.'
    return render_template('auth/login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            try:
                conn.execute('INSERT INTO users (username, password) VALUES (?, ?)',
                             (username, generate_password_hash(password)))
                conn.commit()
                return redirect(url_for('login'))
            except sqlite3.IntegrityError:
                error = 'Username already exists.'
    return render_template('auth/signup.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
