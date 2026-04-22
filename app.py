import streamlit as st
import anthropic
import io
import os
import csv

# ── PDF extraction ────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                if t:
                    text_parts.append(t)
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        clean = [str(c).strip() if c else "" for c in row]
                        text_parts.append(" | ".join(clean))
        return "\n".join(text_parts)
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def extract_text_from_csv(file_bytes: bytes) -> str:
    try:
        content = file_bytes.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(content))
        rows = [" | ".join(row) for row in reader]
        return "\n".join(rows)
    except Exception as e:
        return f"[CSV extraction error: {e}]"


def extract_text(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    raw = uploaded_file.read()
    if name.endswith(".pdf"):
        return extract_text_from_pdf(raw)
    if name.endswith(".csv"):
        return extract_text_from_csv(raw)
    # plain text / txt
    return raw.decode("utf-8", errors="replace")


# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """You are a highly skilled financial analyst and forensic accountant.
Your task is to analyse a company's financial statements (Income Statement, Balance Sheet,
and Cash Flow Statement) and extract key financial data, then provide a structured output
and a clear, insightful analysis.

IMPORTANT:
- Be precise and conservative. Do not invent numbers.
- If a number is missing, state "Not provided".
- Standardise all extracted values into clean, readable format.
- Focus on what actually matters economically, not just accounting presentation.

STEP 1: EXTRACT KEY METRICS
From the statements provided, extract and clearly present:

Profitability:
- Revenue
- Cost of Goods Sold (COGS)
- Gross Profit
- Operating Expenses
- EBITDA (if possible, otherwise approximate)
- Net Profit
- Tax Expense

Cash Flow:
- Operating Cash Flow
- Investing Cash Flow
- Financing Cash Flow
- Net Change in Cash

Balance Sheet:
- Cash
- Accounts Receivable
- Inventory
- Accounts Payable
- Total Debt
- Total Assets
- Total Liabilities
- Equity

Derived / Analytical:
- Gross Margin
- Net Margin
- Working Capital (Current Assets - Current Liabilities)
- Operating Working Capital (AR + Inventory - AP)
- Cash Conversion (compare Net Profit vs Operating Cash Flow)

STEP 2: NORMALISED SUMMARY TABLE
Create a clean, structured table like this:
=== FINANCIAL SUMMARY ===
[Clearly formatted table of all extracted and calculated metrics]

STEP 3: ANALYSIS (THIS IS THE MOST IMPORTANT PART)
Write a concise but sharp analysis covering:
1. Profit Quality — Is profit real or accounting-driven? Compare net profit vs cash flow. Highlight red flags.
2. Cash Health — Is the business generating cash? Any reliance on financing?
3. Working Capital Dynamics — Is cash being trapped in receivables/inventory? Is the business funding customers?
4. Cost Structure — Are margins strong or under pressure? Any notable inefficiencies?
5. Balance Sheet Strength — Debt levels and risk. Liquidity position.

STEP 4: "WHAT IS REALLY GOING ON"
Provide a blunt, investor-style interpretation:
- What kind of business is this really?
- Is it healthy, fragile, or misleading?
- What would concern a private equity investor?

STEP 5: RED FLAGS & KEY INSIGHTS
List:
- Top 3 risks
- Top 3 positive signals

OUTPUT STYLE:
- Structured
- No fluff
- Clear headings
- Analytical, not descriptive
- Think like a private equity investor reviewing a deal
"""


# ── Claude API call ───────────────────────────────────────────────────────────
def analyse_financials(financial_text: str, api_key: str) -> str:
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Please analyse the following financial statements:\n\n{financial_text}",
            }
        ],
    )
    return message.content[0].text


# ── Section parser ────────────────────────────────────────────────────────────
def parse_sections(analysis: str) -> dict:
    """Split raw analysis text into labelled sections."""
    sections = {
        "summary": "",
        "analysis": "",
        "whats_going_on": "",
        "red_flags": "",
        "raw": analysis,
    }

    lines = analysis.split("\n")
    current = "summary"
    buffer: list[str] = []

    def flush(key):
        sections[key] = "\n".join(buffer).strip()
        buffer.clear()

    for line in lines:
        upper = line.upper()
        if "STEP 3" in upper or "ANALYSIS" in upper and "STEP 3" in upper:
            flush(current); current = "analysis"
        elif "STEP 4" in upper or "WHAT IS REALLY GOING ON" in upper:
            flush(current); current = "whats_going_on"
        elif "STEP 5" in upper or "RED FLAGS" in upper:
            flush(current); current = "red_flags"
        buffer.append(line)

    flush(current)
    return sections


# ── Streamlit UI ──────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Financial Statement Analyzer",
        page_icon="📊",
        layout="wide",
    )

    # ── Custom CSS ──────────────────────────────────────────────────────────
    st.markdown(
        """
        <style>
        /* ── global ── */
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .main { background: #0f1117; }

        /* ── hero header ── */
        .hero {
            background: linear-gradient(135deg, #1a1f2e 0%, #0d1117 100%);
            border: 1px solid #2d3748;
            border-radius: 16px;
            padding: 2.5rem 2rem;
            margin-bottom: 2rem;
            text-align: center;
        }
        .hero h1 {
            font-size: 2.4rem;
            font-weight: 700;
            color: #f0f6fc;
            margin: 0 0 0.5rem 0;
            letter-spacing: -0.5px;
        }
        .hero p { color: #8b949e; font-size: 1.05rem; margin: 0; }
        .hero .badge {
            display: inline-block;
            background: rgba(56,189,248,0.12);
            color: #38bdf8;
            border: 1px solid rgba(56,189,248,0.25);
            border-radius: 20px;
            padding: 0.2rem 0.8rem;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.5px;
            margin-bottom: 1rem;
        }

        /* ── upload cards ── */
        .upload-grid { display: flex; gap: 1rem; flex-wrap: wrap; }
        .upload-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1.2rem 1.5rem;
            flex: 1;
            min-width: 220px;
        }
        .upload-card h4 { color: #e6edf3; margin: 0 0 0.3rem 0; font-size: 0.95rem; }
        .upload-card p  { color: #6e7681; font-size: 0.82rem; margin: 0; }

        /* ── section cards ── */
        .section-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 1.5rem 1.8rem;
            margin-bottom: 1.5rem;
        }
        .section-card h2 {
            color: #f0f6fc;
            font-size: 1.15rem;
            font-weight: 600;
            margin: 0 0 1rem 0;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .section-card pre {
            background: #0d1117;
            border: 1px solid #21262d;
            border-radius: 8px;
            padding: 1rem;
            color: #c9d1d9;
            font-size: 0.85rem;
            white-space: pre-wrap;
            word-break: break-word;
            overflow: auto;
        }

        /* ── metric pill row ── */
        .metric-row { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 1rem; }
        .metric-pill {
            background: #1c2128;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 0.6rem 1rem;
            min-width: 150px;
        }
        .metric-pill .label { color: #6e7681; font-size: 0.75rem; margin-bottom: 0.2rem; }
        .metric-pill .value { color: #58a6ff; font-size: 1rem; font-weight: 600; }

        /* ── pill tags ── */
        .tag-risk {
            display: inline-block;
            background: rgba(248,81,73,0.12);
            color: #f85149;
            border: 1px solid rgba(248,81,73,0.3);
            border-radius: 6px;
            padding: 0.25rem 0.7rem;
            font-size: 0.82rem;
            margin: 0.2rem;
        }
        .tag-positive {
            display: inline-block;
            background: rgba(63,185,80,0.12);
            color: #3fb950;
            border: 1px solid rgba(63,185,80,0.3);
            border-radius: 6px;
            padding: 0.25rem 0.7rem;
            font-size: 0.82rem;
            margin: 0.2rem;
        }

        /* ── analyse button ── */
        div[data-testid="stButton"] > button {
            background: linear-gradient(135deg, #238636 0%, #2ea043 100%);
            color: white;
            border: none;
            border-radius: 10px;
            padding: 0.7rem 2.5rem;
            font-size: 1rem;
            font-weight: 600;
            letter-spacing: 0.3px;
            cursor: pointer;
            width: 100%;
            transition: opacity 0.2s;
        }
        div[data-testid="stButton"] > button:hover { opacity: 0.85; }

        /* ── text area ── */
        textarea {
            background: #0d1117 !important;
            border: 1px solid #30363d !important;
            color: #c9d1d9 !important;
            border-radius: 8px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # ── Hero ────────────────────────────────────────────────────────────────
    st.markdown(
        """
        <div class="hero">
            <div class="badge">POWERED BY CLAUDE AI</div>
            <h1>📊 Financial Statement Analyzer</h1>
            <p>Upload financial statements and get institutional-grade forensic analysis in seconds.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── API Key ─────────────────────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        with st.expander("🔑 API Key Configuration", expanded=True):
            api_key = st.text_input(
                "Anthropic API Key",
                type="password",
                placeholder="sk-ant-...",
                help="Your key is never stored. Set ANTHROPIC_API_KEY env var to skip this.",
            )
        if not api_key:
            st.info("Enter your Anthropic API key above to get started.", icon="ℹ️")

    st.divider()

    # ── Input section ───────────────────────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 📁 Upload Financial Statements")
        st.caption("Supported formats: PDF, CSV, TXT — upload one or more documents")

        uploaded_files = st.file_uploader(
            "Drop files here or click to browse",
            type=["pdf", "csv", "txt"],
            accept_multiple_files=True,
            label_visibility="collapsed",
        )

        if uploaded_files:
            for f in uploaded_files:
                size_kb = len(f.getvalue()) / 1024
                icon = "📄" if f.name.endswith(".pdf") else "📋"
                st.markdown(
                    f"<small style='color:#8b949e'>{icon} {f.name} — {size_kb:.1f} KB</small>",
                    unsafe_allow_html=True,
                )

    with col_right:
        st.markdown("### ✍️ Or Paste Financial Data")
        st.caption("Paste raw text, CSV rows, or any formatted financial data")
        pasted_text = st.text_area(
            "Paste here",
            height=180,
            placeholder="Revenue: $10.5M\nCOGS: $6.2M\nNet Profit: $1.8M\n...",
            label_visibility="collapsed",
        )

    st.divider()

    # ── Analyse button ───────────────────────────────────────────────────────
    _, btn_col, _ = st.columns([1, 2, 1])
    with btn_col:
        analyse_clicked = st.button("⚡ Analyse Financial Statements", use_container_width=True)

    # ── Analysis ─────────────────────────────────────────────────────────────
    if analyse_clicked:
        if not api_key:
            st.error("Please provide your Anthropic API key.")
            st.stop()

        # Combine all input sources
        all_text_parts = []

        if uploaded_files:
            for uf in uploaded_files:
                uf.seek(0)
                extracted = extract_text(uf)
                all_text_parts.append(f"=== {uf.name} ===\n{extracted}")

        if pasted_text.strip():
            all_text_parts.append(f"=== Pasted Data ===\n{pasted_text.strip()}")

        if not all_text_parts:
            st.warning("Please upload at least one file or paste financial data.")
            st.stop()

        combined_text = "\n\n".join(all_text_parts)

        with st.spinner("Analysing financial statements with Claude…"):
            try:
                raw_analysis = analyse_financials(combined_text, api_key)
            except anthropic.AuthenticationError:
                st.error("Invalid API key. Please check your Anthropic API key.")
                st.stop()
            except anthropic.RateLimitError:
                st.error("Rate limit reached. Please wait a moment and try again.")
                st.stop()
            except Exception as e:
                st.error(f"Error calling Claude API: {e}")
                st.stop()

        sections = parse_sections(raw_analysis)

        st.success("Analysis complete!", icon="✅")
        st.divider()

        # ── 1. Financial Summary ───────────────────────────────────────────
        st.markdown(
            "<div class='section-card'><h2>📋 Financial Summary Table</h2>",
            unsafe_allow_html=True,
        )
        summary_text = sections["summary"] or raw_analysis.split("STEP 3")[0]
        st.markdown(f"<pre>{summary_text}</pre>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # ── 2. Analysis ────────────────────────────────────────────────────
        analysis_text = sections["analysis"]
        if analysis_text:
            st.markdown(
                "<div class='section-card'><h2>🔍 Detailed Analysis</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(analysis_text)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── 3. What's really going on ──────────────────────────────────────
        wgo_text = sections["whats_going_on"]
        if wgo_text:
            st.markdown(
                "<div class='section-card'><h2>🎯 What Is Really Going On</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(wgo_text)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── 4. Red flags & insights ────────────────────────────────────────
        rf_text = sections["red_flags"]
        if rf_text:
            st.markdown(
                "<div class='section-card'><h2>🚦 Red Flags & Key Insights</h2>",
                unsafe_allow_html=True,
            )
            st.markdown(rf_text)
            st.markdown("</div>", unsafe_allow_html=True)

        # ── 5. Full raw output (expandable) ───────────────────────────────
        with st.expander("📄 Full Raw Analysis Output"):
            st.text(raw_analysis)

        # ── Download ───────────────────────────────────────────────────────
        st.download_button(
            label="⬇️ Download Full Analysis (.txt)",
            data=raw_analysis,
            file_name="financial_analysis.txt",
            mime="text/plain",
            use_container_width=True,
        )

    # ── Footer ───────────────────────────────────────────────────────────────
    st.divider()
    st.markdown(
        "<p style='text-align:center;color:#484f58;font-size:0.8rem;'>"
        "Financial Statement Analyzer · Powered by Anthropic Claude · "
        "Not financial advice — for analytical purposes only."
        "</p>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
