# India Innovates 2026 — Screening Evaluator

A Streamlit app that scores India Innovates 2026 competition submissions and gives each team an **IN** or **OUT** decision.

## What it does

Upload a batch of PPT files (one per team). For each submission the app:

1. Extracts the slide text and sends it to an OpenAI model to score **PPT quality** and **problem-statement alignment**.
2. Lets a human reviewer rate the **prototype / GitHub link** and optional **media** (video / demo).
3. Adds the scores, caps the total at 1.00, and marks the team **IN** (≥ 0.60) or **OUT**.

Results are saved to a local SQLite database and can be exported as CSV or a ZIP of per-team JSON files.

See [`marking_scheme.md`](marking_scheme.md) for the exact score breakdown.

## Requirements

- Python 3.10+
- An OpenAI API key

## Setup

Create a `requirements.txt`:

```
streamlit>=1.35
pypdf>=4.0
openai>=1.30
tiktoken>=0.7
pandas>=2.0
```

Then install:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
export OPENAI_API_KEY="sk-..."
streamlit run ii2026_evaluator.py
```

Open `http://localhost:8501` in your browser.

## Deploying on a server

> **Note:** binding to `0.0.0.0` exposes the app on all network interfaces. Restrict access via firewall rules (allow only trusted IPs) or put it behind a reverse proxy with authentication.

```bash
# keep it alive with tmux
tmux new -s evaluator
streamlit run ii2026_evaluator.py --server.port 8501 --server.address 0.0.0.0
# Ctrl+B then D to detach

# allow only trusted IPs — do NOT open 8501 to the whole internet
ufw allow from <your-ip> to any port 8501
```
