# India Innovates 2026 — Marking Scheme

## Score Architecture

Total = 1.00 · **IN threshold: ≥ 0.60**

| Component | Max | Rater | Required? |
|-----------|-----|-------|-----------|
| Media (video/audio/demo) | +0.25 bonus | Human | ❌ Optional — missing = 0, no penalty |
| Prototype + GitHub link | 0.35 | Human | ✅ Mandatory |
| PPT Quality | 0.30 | LLM | — |
| PS Alignment | 0.35 | LLM | — |

Base score (proto + PPT + align) caps at **1.00**. Media is additive bonus, total capped at 1.00.

---

## Media Bonus — Optional (Human)

Review the video / audio / demo link if submitted. Missing = 0, **no penalty**.

| Rating | Meaning | Score |
|--------|---------|-------|
| `0` | Not submitted | 0.00 |
| `1` | Submitted but barely shows the product, low quality, irrelevant | 0.10 |
| `5` | Clear working demo, polished, shows real output | 0.25 |

---

## Q1 — Prototype + GitHub (Human) · max 0.35

Check the submitted GitHub repo and/or live prototype link. **Mandatory hard gate: rating = 0 → auto-OUT, score computation is skipped entirely.**

| Rating | Meaning | Score |
|--------|---------|-------|
| `0` | Neither submitted | 0.00 |
| `1` | Only one present, OR both broken / empty repo / no commits | 0.10 |
| `5` | Both present, GH has real code + commits, proto is accessible | 0.35 |

---

## Q2 — PPT Quality (LLM) · max 0.30

LLM checks all five required content slides: Problem Statement · Solution · Architecture · Tech Used · Feature/USP.

| LLM Raw | Meaning | Score |
|---------|---------|-------|
| 0 | All placeholder/empty/gibberish | 0.00 |
| 2 | 1–2 slides with real text; rest template | 0.06 |
| 4 | Majority filled but shallow/vague ("we use AI") | 0.12 |
| 6 | Most slides meaningful; architecture weak; tech generic | 0.18 |
| 8 | Solid throughout; clear architecture; specific tech | 0.24 |
| 10 | Exceptional — every slide detailed, precise, credible | 0.30 |

---

## Q3 — Problem-Statement Alignment (LLM) · max 0.35

LLM compares the solution against the **exact required elements** of the stated problem statement. Heaviest weight, harshest rubric.

| LLM Raw | Meaning | Score |
|---------|---------|-------|
| 0 | Wrong domain / completely off-topic / different problem | **0.00** |
| 2 | Mentions domain but ignores all specific requirements | **0.00** |
| 4 | Partially addresses PS; misses >50% of key requirements | 0.10 |
| 6 | Addresses main thrust; misses 1–2 key requirements | 0.18 |
| 8 | Addresses nearly all requirements with technical specificity | 0.28 |
| 10 | Every single REQUIRED element addressed clearly & concretely | 0.35 |

> **Note:** 0 and 2 both score 0.00. Mentioning the domain without addressing the spec is not worth points. No leniency.

---

## IN/OUT Decision

```
TOTAL ≥ 0.60  →  ✅ IN
TOTAL < 0.60  →  ❌ OUT
```

### Example scenarios

| Media (bonus) | Proto/GH | PPT | Align | Total | Verdict |
|---------------|----------|-----|-------|-------|---------|
| 0→0.00 | 5→0.35 | 10→0.30 | 10→0.35 | 1.00 | ✅ IN — no media, still perfect |
| 0→0.00 | 5→0.35 | 8→0.24 | 6→0.18 | 0.77 | ✅ IN |
| 0→0.00 | 5→0.35 | 6→0.18 | 4→0.10 | 0.63 | ✅ IN — bare minimum |
| 0→0.00 | 0→0.00 | 10→0.30 | 10→0.35 | — | ❌ AUTO-OUT — proto/GH missing, gate fails |
| 5→0.25 | 0→0.00 | 10→0.30 | 10→0.35 | — | ❌ AUTO-OUT — media bonus can't save missing proto/GH |
| 0→0.00 | 1→0.10 | 4→0.12 | 4→0.10 | 0.32 | ❌ OUT |
| 5→0.25 | 1→0.10 | 4→0.12 | 2→0.00 | 0.47 | ❌ OUT — wrong PS kills it |
| 0→0.00 | 5→0.35 | 4→0.12 | 2→0.00 | 0.47 | ❌ OUT — wrong PS kills it even with good proto |

Proto/GH = 0 triggers auto-OUT before any LLM evaluation runs. Wrong PS alignment (raw ≤ 2 = 0.00) makes reaching 0.60 on proto + PPT alone nearly impossible.

---

## Deployment on DigitalOcean Droplet

```bash
# 1. SSH into droplet
ssh root@<your-droplet-ip>

# 2. Set up environment
python3 -m venv venv
source venv/bin/activate
pip install streamlit pypdf openai tiktoken pandas

# 3. Clone / copy app.py to droplet
# (use scp or git)

# 4. Run on port 8501
streamlit run app.py --server.port 8501 --server.address 0.0.0.0

# 5. (Optional) keep it alive with tmux
tmux new -s evaluator
streamlit run app.py --server.port 8501 --server.address 0.0.0.0
# Ctrl+B then D to detach

# 6. Open firewall for port 8501
ufw allow 8501
```

Access via `http://<your-droplet-ip>:8501`

## requirements.txt

```
streamlit>=1.35
pypdf>=4.0
openai>=1.30
tiktoken>=0.7
pandas>=2.0
```