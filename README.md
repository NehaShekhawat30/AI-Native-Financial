# AI-Native Financial Review System

A production-grade Django financial review and analytics application designed for restaurant and hospitality businesses (demonstrated with **NYC Restaurant Co.** for Q1 2026).

The system pairs deterministic accounting engines (written in Python and SQL) with controlled Large Language Model (LLM) capabilities to deliver automated bank statement ingestion, two-pass categorization, a drillable monthly P&L statement, material variance analysis, an anomaly review queue, and an AI conversational financial analyst grounded in tool calling and numeric verification guardrails.

---

## What the App Does

1. **Bank Statement Ingestion**: Ingests raw bank and credit card CSV exports, cleans transaction dates and currencies into Python `Decimal` objects, tracks original `source_row` indices, and automatically skips exact duplicate transactions.
2. **Two-Pass Categorization**:
   - **Pass 1 (Rules Engine)**: High-speed, deterministic keyword matching that classifies known recurring vendors (food suppliers, POS deposits, utilities, payroll) with 100% confidence.
   - **Pass 2 (LLM Batch Engine)**: Calls Google Gemini 2.5 Flash in batches for unmatched rows, requiring strict JSON schemas, constrained category choices, confidence scores (0.0–1.0), and one-line reasoning. Rows with confidence under 0.70 are flagged for human review.
3. **Interactive Transactions Ledger**: Search, filter by month/category/review status, and reclassify transactions. Changing a category immediately adjusts P&L calculations, updates balance sheet flags (`in_pnl`), logs an immutable audit entry in the `Correction` model, and provides a 1-click option to apply the correction to all matching historical descriptions.
4. **Deterministic Monthly P&L**: Computes standard 6-line P&L statements (Revenue, COGS, Gross Profit, Payroll, Operating Expenses, Operating Profit) for each month. Costs are displayed as positive numbers with clear sign conventions. Every single figure is a clickable link filtering the ledger to show backing transactions.
5. **Material Variance Detection**: Programmatically flags month-over-month shifts exceeding configurable thresholds (>10% and >$2,000). Calculates primary category drivers and isolates the top 5 transactions behind each shift, passing only structured data to the LLM for concise 2–3 sentence executive summaries.
6. **"Needs Review" Anomaly Queue**: A rule-based review pipeline detecting low-confidence AI predictions, statistically unusual transaction amounts (>1.5× category average and >$1,000 difference), duplicate candidates, non-P&L balance sheet reclassifications, and missing fields.
7. **AI Conversational Analyst**: A chat interface powered by Gemini tool calling with 5 database tools (`get_pnl`, `compare_months`, `get_transactions`, `get_review_items`, `get_variances`). Answers are generated strictly from tool results with mandatory transaction citations.
8. **Hallucination Guardrails & Test Suite**: A post-generation verification guardrail inspects every number in chat answers against the tool results of that turn, triggering a single correction retry or a safe fallback message. Backed by 5 comprehensive unit tests.

---

## Project Structure

```text
Finzcard/
├── manage.py                                      # Django CLI management script
├── requirements.txt                               # Production Python dependencies
├── Procfile                                       # Process definition for Render/Railway (gunicorn)
├── build.sh                                       # Automated build script for cloud deployment
├── sample_transactions.csv                        # Clean copy of NYC Restaurant Co. Q1 2026 data
├── NYC Restaurant Co. - Raw Transactions...csv    # Original raw source transactions
├── .env.example                                   # Sample environment configuration
├── config/                                        # Django project configuration
│   ├── __init__.py
│   ├── settings.py                                # Production settings (WhiteNoise, dj-database-url)
│   ├── urls.py                                    # Root URL routing
│   ├── wsgi.py                                    # WSGI entry point
│   └── asgi.py                                    # ASGI entry point
└── finance/                                       # Core finance app
    ├── models.py                                  # Category, Transaction, and Correction models
    ├── admin.py                                   # Django admin registration
    ├── rules.py                                   # Pass 1 deterministic categorization rules
    ├── views.py                                   # View controllers (P&L, Ledger, Review, Chat)
    ├── urls.py                                    # Finance URL patterns
    ├── tests.py                                   # Step 9 unit test suite (5 core tests)
    ├── management/
    │   └── commands/
    │       ├── seed_categories.py                 # Seeds 26 Chart of Accounts categories
    │       ├── import_transactions.py             # CSV ingestion command
    │       ├── categorize_transactions.py         # Runs Pass 1 rules & Pass 2 LLM batch engine
    │       └── setup_demo.py                      # One-command demo initialization
    ├── services/
    │   ├── importer.py                            # Decimal currency & date parsing, duplicate skipping
    │   ├── categorizer.py                         # Two-pass categorization coordinator
    │   ├── llm_client.py                          # Gemini batch categorization & structured validation
    │   ├── pnl.py                                 # Deterministic monthly P&L calculations (Python/SQL)
    │   ├── variances.py                           # Material variance detection & driver analysis
    │   ├── review_detector.py                     # Rule-based anomaly detection for Needs Review queue
    │   ├── analyst_tools.py                       # The 5 database tools exposed to LLM function calling
    │   ├── chat_analyst.py                        # Chat orchestrator with dual-mode tool routing
    │   └── guardrails.py                          # Numeric extraction and verification guardrails
    └── templates/
        └── finance/
            ├── base.html                          # Premium dark-mode base layout
            ├── pnl.html                           # Monthly P&L table with drill-down links
            ├── transactions.html                  # Ledger table with filters & edit modal
            ├── variances.html                     # Material variance cards with top 5 drivers
            ├── needs_review.html                  # Anomaly review queue with resolve actions
            ├── chat.html                          # Conversational AI financial analyst UI
            └── upload.html                        # CSV upload interface
```

---

## Setup and Run Instructions

### 1. Prerequisites
- Python 3.11, 3.12, 3.13, or 3.14
- Git

### 2. Local Environment Setup

Clone the repository and create a virtual environment:
```bash
git clone <repo-url>
cd Finzcard

# Create and activate virtual environment
python -m venv .venv

# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1

# On macOS/Linux:
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Copy the sample environment file to `.env`:
```bash
cp .env.example .env
```

Open `.env` and fill in your keys:
```ini
SECRET_KEY=your-secure-random-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
DATABASE_URL=
GEMINI_API_KEY=your-google-gemini-api-key
```
*(Note: If `DATABASE_URL` is left empty, the application automatically uses local SQLite `db.sqlite3`)*.

### 4. One-Command Demo Setup

Run the unified demo initialization command:
```bash
python manage.py setup_demo
```
This single command automatically:
1. Applies all database migrations.
2. Seeds the 26 Chart of Accounts categories (Revenue, COGS, Payroll, Opex, Non-P&L).
3. Ingests all 181 transactions from `NYC Restaurant Co. - Raw Transactions.xlsx - Sheet1.csv`.
4. Runs the two-pass categorization engine.

### 5. Running the Application

Start the development server:
```bash
python manage.py runserver
```

Open your browser and navigate to:
- **P&L Statement**: `http://127.0.0.1:8000/pnl/`
- **Transactions Ledger**: `http://127.0.0.1:8000/transactions/`
- **Material Variances**: `http://127.0.0.1:8000/variances/`
- **Needs Review Queue**: `http://127.0.0.1:8000/needs-review/`
- **AI Financial Analyst**: `http://127.0.0.1:8000/chat/`
- **CSV Uploader**: `http://127.0.0.1:8000/upload/`

### 6. Running Unit Tests

Run the test suite to verify accounting integrity and guardrails:
```bash
python manage.py test finance -v 2
```

---

## Deployment (Render or Railway)

### Deploying to Render
1. Push your repository to GitHub or GitLab.
2. In the [Render Dashboard](https://dashboard.render.com/), click **New +** &rarr; **Web Service**.
3. Select your repository and specify:
   - **Environment**: `Python 3`
   - **Build Command**: `./build.sh` (or `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py setup_demo`)
   - **Start Command**: `gunicorn config.wsgi:application`
4. Add the following **Environment Variables**:
   - `SECRET_KEY`: `<generated-secret-key>`
   - `DEBUG`: `False`
   - `ALLOWED_HOSTS`: `.onrender.com` (or omit, as `settings.py` auto-detects Render)
   - `CSRF_TRUSTED_ORIGINS`: `https://*.onrender.com`
   - `GEMINI_API_KEY`: `<your-gemini-api-key>`
   - `DATABASE_URL`: *(Optional: paste Render PostgreSQL Internal Connection String, or omit to run on SQLite)*
5. Click **Deploy**. The application builds, collects static files via WhiteNoise, runs `setup_demo`, and goes live immediately.

---

## Key Technical Decisions

1. **Python `Decimal` for All Monetary Calculations**:
   Floats suffer from binary floating-point rounding errors (e.g. `0.1 + 0.2 != 0.3`). All currency fields in models, database aggregations, and calculations strictly use `Decimal('0.01')` to ensure penny-perfect financial reconciliation.
2. **Strict Separation of Deterministic Math vs. AI Language**:
   The LLM is strictly prohibited from performing arithmetic or generating financial totals. All numbers shown in P&L statements, variance calculations, and chat responses are produced directly by SQL/Python queries against the `Transaction` table.
3. **Two-Pass Categorization for Latency and Cost Efficiency**:
   Pass 1 handles over 93% of typical restaurant transactions via simple keyword matching with 0ms LLM latency and zero API cost. Pass 2 delegates only ambiguous rows to Gemini in structured batches with confidence scoring.
4. **Immutable Audit Trail for Reclassifications**:
   Whenever a user edits a category from the UI, the application saves the change, updates `in_pnl`, sets `status = corrected`, and logs a new `Correction` record storing `old_category`, `new_category`, and a timestamp.
5. **Dual-Mode AI Analyst Routing**:
   The chat analyst supports real-time multi-turn function calling via the official `google-genai` SDK (`gemini-2.5-flash`). If no API key is provided or offline operation is required, the controller falls back to a deterministic tool router that parses intents, invokes the same 5 database tools, and formats verified answers citing exact transaction IDs.

---

## Where and why AI is used

1. **Pass 2 Transaction Categorization (`finance/services/llm_client.py`)**:
   - *Where*: Applied only to transactions that fail to match any keyword rule in Pass 1.
   - *Why*: Unstructured bank descriptors (e.g. `SQ *LITTLE CUPCAKE`, `HUDSON YARDS CATERING DEP`, `SPOTIFY USA`) contain natural language variations and abbreviations that rule-based systems cannot anticipate. The LLM performs semantic classification against the predefined Chart of Accounts and assigns a confidence score and a concise rationale.
2. **Material Variance Plain-English Summaries (`finance/services/variances.py`)**:
   - *Where*: Attached to each detected material variance (>10% and >$2,000).
   - *Why*: Executive stakeholders need clear, contextual 2–3 sentence explanations of *why* an expense or revenue line moved. The LLM receives pre-computed driver categories and top 5 transactions, synthesizing this structured data into readable commentary.
3. **Conversational AI Financial Analyst (`finance/services/chat_analyst.py`)**:
   - *Where*: Inside the `/chat/` conversational interface.
   - *Why*: Natural language is the most intuitive interface for financial inquiries (e.g. *"Why did operating profit change between February and March?"* or *"What drove the increase in food costs?"*). AI is used to parse user intent, select the appropriate database tools (`get_pnl`, `compare_months`, `get_transactions`, `get_review_items`, `get_variances`), and present findings with clear citations.

---

## Where and why deterministic code is used

1. **Transaction Ingestion & Data Normalization (`finance/services/importer.py`)**:
   - *Where*: Raw CSV parsing, date normalization, negative amount handling (`-$500`, `($500)`), and duplicate checking.
   - *Why*: Deterministic code prevents duplicate records, guarantees that every row receives its true `source_row` index, and prevents data corruption before records reach the database.
2. **Pass 1 Keyword Rules (`finance/rules.py`)**:
   - *Where*: Initial categorization pass matching known vendors (Sysco, Toast POS, Gusto, ConEd).
   - *Why*: High-volume recurring transactions require instantaneous, deterministic classification with 100% confidence, zero API latency, and zero token costs.
3. **Monthly P&L Aggregations (`finance/services/pnl.py`)**:
   - *Where*: Calculating monthly Revenue, COGS, Gross Profit, Payroll, Operating Expenses, and Operating Profit.
   - *Why*: Financial accounting requires absolute mathematical correctness. Deterministic SQL queries (`Sum('amount')`) and Python `Decimal` operations guarantee that totals equal the exact sum of transactions and comply with GAAP principles.
4. **Material Variance & Driver Detection (`finance/services/variances.py`)**:
   - *Where*: Threshold comparisons (>10% and >$2,000) and ranking category deltas and top 5 transactions.
   - *Why*: Materiality thresholds must follow rigid business definitions. Deterministic sorting isolates the exact transactions that caused the financial shift.
5. **Anomaly Detection Queue (`finance/services/review_detector.py`)**:
   - *Where*: Flagging low-confidence classifications, unusual amounts (>1.5× category average and >$1,000 difference), potential duplicates, and non-P&L balance sheet items.
   - *Why*: Audit compliance requires predictable, transparent, and reproducible anomaly detection criteria rather than unpredictable heuristics.

---

## How wrong or unsupported answers are prevented

1. **Strict Category Whitelisting & Schema Enforcement (`finance/services/llm_client.py`)**:
   The categorization prompt enforces a strict JSON schema containing only valid category names from the database. Any category returned by the LLM that is not in the system's Chart of Accounts is rejected by code, preventing hallucinated accounts.
2. **Constrained Tool Calling Execution (`finance/services/analyst_tools.py`)**:
   The AI analyst is instructed via system prompt to answer *only* from tool outputs and never from its internal pre-trained memory. If tools do not contain the answer, it is instructed to explicitly state: *"I cannot answer this from the financial database."*
3. **Mandatory Transaction Evidence & Links**:
   Every response referencing numbers must cite backing Transaction IDs (e.g. `Tx #170`) or provide direct markdown links to the filtered transaction ledger.
4. **Non-P&L Isolation**:
   Non-operating cash transfers (equipment purchases, sales tax remittances, owner distributions, loan repayments) are tagged `in_pnl = False` by code. They are systematically excluded from P&L calculations, preventing balance sheet transactions from distorting profitability.

---

## How output is verified

1. **Number Verification Guardrail (`finance/services/guardrails.py`)**:
   - After each chat response is generated, a regex engine (`extract_numbers_from_text`) extracts every currency value, decimal, and percentage in the answer.
   - A recursive extractor (`extract_numbers_from_tool_data`) scans all structured data returned by that turn's tool calls.
   - If any number in the model's answer does not exist in the tool results, the system **retries once** with an explicit error correction prompt.
   - If unverified numbers persist after the retry, the response is discarded and replaced with a safe fallback message directing the user to the verified P&L and ledger pages.
2. **Automated Unit Test Suite (`finance/tests.py`)**:
   A dedicated test suite validates 5 critical system invariants:
   - `test_pnl_totals_equal_sum_of_transactions`: Verifies that Revenue, COGS, Gross Profit, and Operating Profit match the sum of backing database rows.
   - `test_changing_category_updates_pnl`: Verifies that recategorizing a transaction immediately updates P&L values and writes a `Correction` audit record.
   - `test_non_pnl_rows_are_excluded`: Proves that non-P&L transactions (e.g. a $5,000 oven purchase) are strictly excluded from P&L totals.
   - `test_variance_drivers_add_up_to_change`: Verifies that identified driver categories accurately account for month-over-month line deltas.
   - `test_number_checker_blocks_made_up_figure`: Confirms that the guardrail successfully detects and blocks hallucinated numbers.
3. **Interactive UI Auditability**:
   Every number in the monthly P&L grid and variance analysis cards is an interactive hyperlink (`/transactions/?month=...&category=...`). Clicking any figure displays the exact ledger rows that produced it.
