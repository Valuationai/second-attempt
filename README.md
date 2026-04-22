# 📊 Financial Statement Analyzer

AI-powered forensic financial analysis using Anthropic Claude.

---

## Quick Start (Local)

```bash
# 1. Clone / download the files
# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."   # Mac/Linux
set ANTHROPIC_API_KEY=sk-ant-...        # Windows CMD

# 4. Run
streamlit run app.py
```

The app will open at http://localhost:8501.  
If you skip step 3, the app will prompt you for the key in the browser.

---

## Deploy to Streamlit Cloud

1. Push `app.py` and `requirements.txt` to a GitHub repo.
2. Go to https://share.streamlit.io → **New app** → select your repo.
3. In **Advanced settings → Secrets**, add:

```toml
ANTHROPIC_API_KEY = "sk-ant-..."
```

4. Click **Deploy**. Done.

---

## Features

| Feature | Detail |
|---|---|
| File formats | PDF, CSV, TXT |
| Multi-file upload | Combine IS + BS + CF in one run |
| Text paste | Works without any file upload |
| Analysis depth | 5-step PE-style forensic analysis |
| Download | Full analysis as `.txt` |

---

## How It Works

1. Files are parsed locally (pdfplumber for PDFs, built-in for CSV/TXT).
2. Extracted text is sent to Claude with a detailed forensic-accounting system prompt.
3. Claude returns a structured analysis with summary table, metrics, narrative, and red flags.
4. The app splits the response into labelled sections and renders each one.

---

## Notes

- Your API key is never stored by the app.
- Analysis quality depends on the completeness of the uploaded statements.
- This tool is for analytical purposes only — not financial advice.
