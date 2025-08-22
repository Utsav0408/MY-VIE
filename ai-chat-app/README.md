# AI Chat App (Flask + Gemini)

A polished Flask app that talks to Google's Gemini via the official `google-generativeai` SDK,
featuring a modern, glassy UI with animated 3D gradients.

## Setup

1) Make a virtual environment (recommended) and install deps:
```bash
pip install -r requirements.txt
```

2) Copy `.env.example` to `.env` and put your real keys:
```
GEMINI_API_KEY=your_key_here
FLASK_SECRET_KEY=any_secret_string
# MODEL_NAME=gemini-1.5-flash   # optional override
```

3) Run the server:
```bash
python app.py
```

4) Open http://127.0.0.1:5000 in your browser.

## Notes

- If you get a 503 in /ask, ensure your `.env` has a valid `GEMINI_API_KEY`.
- You can switch the model via `MODEL_NAME`.
