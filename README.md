# 🧠 AI Code Annotator

An AI-powered web tool built with Flask and Google Gemini that automatically annotates source code, analyzes time/space complexity, and generates professional README and `requirements.txt` files for your projects.

---

## ✨ Features

- **Auto Code Annotation** — Adds clear, concise block comments to your code explaining each logical section
- **Complexity Analysis** — Provides time and space complexity (Big-O) with a plain-English program explanation
- **Multi-Language Support** — Detects and handles Python, Java, C++, and JavaScript using weighted pattern scoring
- **README Generator** — Generates a professional `README.md` from your project code
- **requirements.txt Generator** — Extracts third-party pip dependencies automatically
- **File & ZIP Upload** — Accepts single code files or a `.zip` of an entire project
- **Downloadable Output** — Download the annotated file in its original language format
- **Loading Indicator** — Visual feedback while the AI processes your code
- **Secure File Handling** — ZIP path traversal protection and filename sanitization

---

## 🖥️ Demo

| Code Annotator | README Generator |
|---|---|
| Paste or upload code → get annotated output + complexity | Paste or upload project → get README + requirements |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, Flask |
| AI Model | Google Gemini 2.5 Flash |
| Frontend | HTML, CSS, Vanilla JS (Jinja2 templates) |
| File Handling | Python `zipfile`, `tempfile`, `werkzeug` |
| Config | `python-dotenv` |

---

## 📁 Project Structure

```
ai-code-annotator/
├── app.py               # Flask backend — routes, language detection, Gemini integration
├── templates/
│   ├── index.html       # Code Annotator UI
│   └── readme.html      # README Generator UI
├── .env              # Environment variables (not committed)
├── requirements.txt
└── README.md
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/ai-code-annotator.git
cd ai-code-annotator
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Mac/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up your Gemini API key

Create a `.env` file in the project root:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

> Get your free API key at [aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)

Add `.env` to `.gitignore` to keep it out of version control:

```
key.env
```

### 5. Run the app

```bash
python app.py
```

Visit `http://127.0.0.1:5000` in your browser.

---

## 🚀 Usage

### Code Annotator (`/`)

1. Paste your code into the text area **or** upload a `.py`, `.java`, `.cpp`, or `.js` file
2. Click **✨ Annotate Code**
3. View the annotated code, program explanation, and complexity analysis
4. Click **⬇ Download Annotated File** to save the output

### README Generator (`/readme`)

1. Paste your project code **or** upload a single file or a `.zip` of your project
2. Click **🚀 Generate Documentation**
3. View and download the generated `README.md` and `requirements.txt`

---

## 🔒 Security

- API key loaded from environment variable — never hardcoded
- ZIP extraction guards against path traversal attacks
- Download filenames are sanitized to prevent header injection
- `debug` mode is controlled via the `FLASK_DEBUG` environment variable

---

## 📦 Requirements

```
flask
google-generativeai
python-dotenv
```

Install with:

```bash
pip install flask google-generativeai python-dotenv
```

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.
