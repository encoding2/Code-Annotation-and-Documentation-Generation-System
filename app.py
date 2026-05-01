from flask import Flask, render_template, request, Response
import google.generativeai as genai
import re
import zipfile
import os
import tempfile
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")
genai.configure(api_key=GEMINI_API_KEY)

MODEL_NAME = "gemini-2.5-flash"

LANGUAGE_EXTENSIONS = {
    "Python": "py",
    "Java": "java",
    "C++": "cpp",
    "JavaScript": "js"
}

# ---------------- SAFE FILENAME ----------------
def sanitize_filename(filename):
    """Strip everything except alphanumerics, dots, dashes, underscores."""
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w.\-]", "_", filename)
    return filename or "download"


# ---------------- ZIP EXTRACTION ----------------
def safe_extract_zip(zip_path, tmpdir):
    """Extract ZIP while blocking path traversal attacks."""
    with zipfile.ZipFile(zip_path, "r") as z:
        for member in z.namelist():
            # Reject absolute paths and any path component that is '..'
            if os.path.isabs(member) or ".." in member.split("/"):
                continue
            dest = os.path.realpath(os.path.join(tmpdir, member))
            if not dest.startswith(os.path.realpath(tmpdir)):
                continue  # would escape tmpdir
            z.extract(member, tmpdir)


# ---------------- FILE READING HELPER ----------------
def extract_code_from_request(req):
    """Return (code_str, error_str). One of them will be None."""
    uploaded_file = req.files.get("file")
    if uploaded_file and uploaded_file.filename:
        if uploaded_file.filename.endswith(".zip"):
            with tempfile.TemporaryDirectory() as tmpdir:
                zip_path = os.path.join(tmpdir, "upload.zip")
                uploaded_file.save(zip_path)
                try:
                    safe_extract_zip(zip_path, tmpdir)
                except zipfile.BadZipFile:
                    return None, "❌ Uploaded file is not a valid ZIP."
                all_code = []
                for root, _, files in os.walk(tmpdir):
                    for fname in files:
                        if fname.endswith((".py", ".java", ".cpp", ".js")):
                            fpath = os.path.join(root, fname)
                            with open(fpath, "r", errors="ignore") as f:
                                all_code.append(f"# File: {fname}\n" + f.read())
                return "\n\n".join(all_code), None
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore"), None

    code = req.form.get("code", "").strip()
    return (code if code else None), None


# ---------------- LANGUAGE DETECTION ----------------
# Each pattern carries a weight: strong/unique signals score 2,
# common-but-useful signals score 1. A language needs >= 4 to match.

LANGUAGE_PATTERNS = {
    "Python": [
        (r"\bdef\s+\w+\s*\(", 2),          # function def
        (r"\bself\b", 2),                   # OOP self
        (r"^\s*import\s+\w+", 1),           # bare import (not Java import)
        (r"^\s*from\s+\w+\s+import\b", 2),  # from X import Y
        (r":\s*\n\s+\S", 2),               # colon-then-indented-block
        (r"\bprint\s*\(", 1),              # print()
        (r"\bTrue\b|\bFalse\b|\bNone\b", 1),  # Python keywords
        (r"#.*$", 1),                      # # comments
    ],
    "Java": [
        (r"\bpublic\s+(class|interface|enum)\b", 2),
        (r"\bSystem\.out\.print", 2),
        (r"\bArrayList<|HashMap<|LinkedList<", 2),
        (r"\bint\[\]|\bString\[\]", 2),
        (r"\bvoid\s+\w+\s*\(", 1),         # void method
        (r"\bnew\s+\w+\s*\(", 1),          # new Object()
        (r"@Override|@SuppressWarnings", 2),
        (r"\bimport\s+java\.", 2),
    ],
    "C++": [
        (r"#include\s*<\w+>", 2),
        (r"\bstd::", 2),
        (r"\bvector\s*<|map\s*<|unordered_map\s*<", 2),
        (r"\bcout\s*<<|\bcin\s*>>", 2),
        (r"\busing\s+namespace\s+std\b", 2),
        (r"::\w+\s*\(", 1),                # scope resolution
        (r"\btemplate\s*<", 2),
        (r"\bnullptr\b|\bNULL\b", 1),
    ],
    "JavaScript": [
        (r"\bconsole\.(log|error|warn)\b", 2),
        (r"=>\s*[\{\(]|=>\s*\w", 2),       # arrow functions
        (r"\bconst\b|\blet\b", 1),
        (r"\bfunction\s+\w+\s*\(", 1),
        (r"\bdocument\.\w+|\bwindow\.\w+", 2),
        (r"\brequire\s*\(|module\.exports\b", 2),
        (r"\bPromise\b|\basync\b|\bawait\b", 2),
        (r"===|!==", 2),                   # strict equality (rare in others)
    ],
}

DETECTION_THRESHOLD = 4


def detect_language(code):
    """
    Return the single best-matching language name, or None if no language
    clears the threshold. Uses weighted pattern scoring and picks the winner
    by highest score to avoid ambiguity (e.g. JS `const` leaking into Python).
    """
    scores = {}
    for lang, patterns in LANGUAGE_PATTERNS.items():
        total = 0
        for pattern, weight in patterns:
            if re.search(pattern, code, re.MULTILINE):
                total += weight
        scores[lang] = total

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    if best_score < DETECTION_THRESHOLD:
        return None

    # Reject ambiguous results: if two languages are within 1 point of
    # each other and both cleared the threshold something is likely mixed.
    runner_up = sorted(scores.values(), reverse=True)[1]
    if runner_up >= DETECTION_THRESHOLD and (best_score - runner_up) <= 1:
        # Fall back to the language whose unique/high-weight signals dominate
        # (still return best_lang — caller can show a warning if needed).
        pass

    return best_lang


# ---------------- PROMPTS ----------------
def build_annotation_prompt(code, language):
    return f"""
Add VERY BRIEF block-style comments explaining each logical part.

STRICT:
- Only block comments
- 1 short line per comment
- No explanations outside code
- No complexity in code

Code Language: {language}

Code:
{code}
"""

def build_explanation_prompt(code):
    return f"""
Explain this program briefly and provide complexity.

FORMAT STRICTLY:

EXPLANATION:
<1 short line>

TIME COMPLEXITY:
<Big-O>

SPACE COMPLEXITY:
<Big-O>

Code:
{code}
"""


# ---------------- ROUTES ----------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/readme")
def readme():
    return render_template("readme.html")


@app.route("/generate_readme", methods=["POST"])
def generate_readme():
    code, err = extract_code_from_request(request)
    if err:
        return render_template("readme.html", error=err)
    if not code:
        return render_template("readme.html", error="⚠ Please provide code input.")

    model = genai.GenerativeModel(MODEL_NAME)

    readme_prompt = f"""
Generate a professional README.md for the following project code.
Include: Project Title, Description, Features, Installation, Usage, and Tech Stack sections.
Use proper Markdown formatting.

Code:
{code}
"""

    requirements_prompt = f"""
List only the third-party pip packages used in this Python code as a requirements.txt file.
One package per line, no versions unless critical. No explanations.

Code:
{code}
"""

    try:
        readme_result = model.generate_content(
            readme_prompt,
            generation_config={"temperature": 0.3}
        ).text

        requirements_result = model.generate_content(
            requirements_prompt,
            generation_config={"temperature": 0.1}
        ).text
    except Exception as e:
        return render_template(
            "readme.html",
            error=f"⚠ Gemini API error: {str(e)}"
        )

    return render_template(
        "readme.html",
        result=readme_result,
        requirements=requirements_result
    )


@app.route("/annotate", methods=["POST"])
def annotate():
    code, err = extract_code_from_request(request)
    if err:
        return render_template("index.html", error=err)
    if not code:
        return render_template("index.html", error="⚠ Please provide code input.")

    language = detect_language(code)
    if not language:
        return render_template("index.html", error="❌ Could not detect a supported language (Python, Java, C++, JavaScript).")

    model = genai.GenerativeModel(MODEL_NAME)

    try:
        # ---- Annotated Code ----
        annotated_code = model.generate_content(
            build_annotation_prompt(code, language),
            generation_config={"temperature": 0.2}
        ).text

        # ---- Explanation + Complexity ----
        explanation_raw = model.generate_content(
            build_explanation_prompt(code),
            generation_config={"temperature": 0.3}
        ).text
    except Exception as e:
        return render_template(
            "index.html",
            error=f"⚠ Gemini API error: {str(e)}"
        )

    explanation = ""
    time_complexity = ""
    space_complexity = ""

    exp_match = re.search(r"EXPLANATION:\s*(.*?)\s*TIME COMPLEXITY:", explanation_raw, re.DOTALL)
    time_match = re.search(r"TIME COMPLEXITY:\s*(.*?)\s*SPACE COMPLEXITY:", explanation_raw, re.DOTALL)
    space_match = re.search(r"SPACE COMPLEXITY:\s*(.*)", explanation_raw, re.DOTALL)

    if exp_match:
        explanation = exp_match.group(1).strip()
    if time_match:
        time_complexity = time_match.group(1).strip()
    if space_match:
        space_complexity = space_match.group(1).strip()

    ext = LANGUAGE_EXTENSIONS.get(language, "txt")
    download_filename = f"annotated_output.{ext}"

    return render_template(
        "index.html",
        result=annotated_code,
        explanation=explanation,
        time_complexity=time_complexity,
        space_complexity=space_complexity,
        download_filename=download_filename
    )


# ---------------- DOWNLOAD ----------------
@app.route("/download_file", methods=["POST"])
def download_file():
    content = request.form.get("content", "")
    raw_filename = request.form.get("filename", "download.txt")
    filename = sanitize_filename(raw_filename)

    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
    )


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true")
