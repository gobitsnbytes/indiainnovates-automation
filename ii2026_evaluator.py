"""
India Innovates 2026 — Screening Evaluator

This implementation follows the current score mappings in marking_scheme.md:
    - Media:      0 / 0.10 / 0.25
    - Prototype:  0 / 0.10 / 0.35
    - PPT:        0 / 0.06 / 0.12 / 0.18 / 0.24 / 0.30
    - Alignment:  0 / 0.00 / 0.10 / 0.18 / 0.28 / 0.35

Prototype + GitHub rating 0 is a mandatory hard gate: auto-OUT and LLM scoring is skipped.
Otherwise, total is capped at 1.00. IN threshold is 0.60.
"""

from __future__ import annotations

import json
import time
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st
import tiktoken
from openai import APIError, OpenAI, RateLimitError
from pptx import Presentation

IN_THRESHOLD = 0.60
MAX_FILES_BATCH = 10
MAX_PPT_TOKENS = 3000
LLM_CONTEXT_SOFT_LIMIT = 7000

MEDIA_SCORE_MAP = {0: 0.00, 1: 0.10, 5: 0.25}
PROTO_SCORE_MAP = {0: 0.00, 1: 0.10, 5: 0.35}
PPT_SCORE_MAP = {0: 0.00, 2: 0.06, 4: 0.12, 6: 0.18, 8: 0.24, 10: 0.30}
ALIGN_SCORE_MAP = {0: 0.00, 2: 0.00, 4: 0.10, 6: 0.18, 8: 0.28, 10: 0.35}

ALLOWED_PPT_RAW = tuple(PPT_SCORE_MAP.keys())
ALLOWED_ALIGN_RAW = tuple(ALIGN_SCORE_MAP.keys())

SLIDE_LABELS = [
    "COVER / TEAM INFO",
    "PROBLEM STATEMENT",
    "SOLUTION",
    "ARCHITECTURE",
    "TECHNOLOGY USED",
    "FEATURE / USP",
    "REFERENCES / LINKS",
    "THANK YOU",
]

REQUIRED_SLIDES = [
    "PROBLEM STATEMENT",
    "SOLUTION",
    "ARCHITECTURE",
    "TECHNOLOGY USED",
    "FEATURE / USP",
]

PLACEHOLDER_FINGERPRINTS = {
    "clearly define the real-world challenge",
    "describe your proposed approach",
    "present the overall system design",
    "list the tools, frameworks",
    "highlight the core features",
    "include resources, research papers",
    "focus on innovation, impact",
    "what makes your idea stand out",
    "mention how each technology contributes",
    "key components, integrations",
    "emphasize its user experience",
    "problem statement",
    "solution",
    "architecture",
    "technology used",
    "feature / usp",
    "feature/usp",
}

PROBLEM_STATEMENTS: dict[str, dict[str, str]] = {
    "Domain 1 — Urban Solutions": {
        "1A · Urban Flooding & Hydrology Engine": (
            "GIS-integrated predictive system identifying 2,500+ urban flood micro-hotspots "
            "from historical rainfall data, terrain elevation, and drainage capacity. "
            "Must generate a ward-level 'Pre-Monsoon Readiness Score' for proactive resource deployment. "
            "REQUIRED: GIS integration, ≥2500 hotspot granularity, multi-source data fusion (rainfall + terrain + drainage), "
            "ward-level scoring output, pre-deployment logic."
        ),
        "1B · Hyper-Local AQI & Pollution Mitigation Dashboard": (
            "Ward-wise real-time air quality system beyond city averages. "
            "ML must detect localized pollution sources (construction dust, biomass burning). "
            "Automated policy recommendations for administrators + health advisories for citizens. "
            "REQUIRED: ward-level granularity, real-time feed, ML source detection, automated policy output, health advisory module."
        ),
        "1C · AI-Driven Circular Waste Intelligence System": (
            "AI-vision + IoT waste tracking: auto-classify waste (biodegradable / recyclable / hazardous) "
            "at source or during collection. Fleet route optimization for emission reduction. "
            "Transparent incentive model rewarding high segregation efficiency. "
            "REQUIRED: AI vision classification (all 3 categories), IoT integration, route optimizer, incentive/reward mechanism."
        ),
        "1D · Dynamic AI Traffic Flow Optimizer & Emergency Grid": (
            "Computer-vision traffic management dynamically adjusting signal timings from live density. "
            "AI-powered green corridor feature for emergency vehicles (ambulance, fire). "
            "REQUIRED: real-time CV, dynamic signal control, live density input, emergency vehicle detection, green corridor routing."
        ),
    },
    "Domain 2 — Digital Democracy": {
        "2A · Global Ontology / Intelligence Graph Engine": (
            "AI engine ingesting structured data, unstructured content, and live feeds across "
            "geopolitics, economics, defense, technology, climate, society — fused into a single "
            "unified, continuously updating intelligence graph for national strategic decision-making. "
            "REQUIRED: multi-domain ingestion, knowledge graph, real-time updates, decision-support interface, India-focused insights."
        ),
        "2B · AI-Driven Booth Management System": (
            "Convert static voter lists into a living Knowledge Graph with booth-level voter categorization "
            "(youth, businessmen, farmers, women). Deliver personalized governance updates to individual devices. "
            "REQUIRED: knowledge graph construction, booth-level segmentation, personalized delivery pipeline, "
            "beneficiary linkage (e.g. Ayushman Bharat), micro-accountability mapping."
        ),
        "2C · Hyper-Local Targeting Engine (Geo-fencing)": (
            "Geo-fencing around public development sites (hospitals, colleges, bridges, infrastructure) "
            "triggering location-based context-aware notifications explaining civic work and impact. "
            "REQUIRED: geo-fence triggers, context-aware notification system, before/after proof delivery, "
            "street-level precision, civic impact transparency."
        ),
        "2D · Secure Blockchain E-Voting System": (
            "Blockchain-based e-voting eliminating logistical barriers with end-to-end encryption "
            "and tamper-proof audit trail for 100% integrity in high-stakes democratic elections. "
            "REQUIRED: blockchain implementation, E2E encryption, immutable audit trail, scalability evidence, "
            "anti-tamper mechanism, voter authentication."
        ),
        "2E · AI-Powered Avatar Platform": (
            "Platform for creating realistic interactive digital avatars that speak, present, "
            "and engage audiences in real time across multiple languages. "
            "REQUIRED: realistic avatar synthesis, real-time interaction, multilingual support, "
            "live presentation capability, governance/education use case demonstrated."
        ),
        "2F · AI Inbound & Outbound Calling Agent": (
            "Multilingual AI calling agent for high-volume phone conversations: public service, "
            "customer support, surveys, grievance redressal, outreach campaigns. "
            "Real-time speech understanding, contextual memory, escalation handling, analytics. "
            "REQUIRED: multilingual ASR/TTS, high-volume architecture, grievance redressal flow, "
            "context memory, escalation logic, analytics dashboard."
        ),
        "2G · Smart Public Service CRM (PS-CRM)": (
            "Centralized command center for citizen complaints: automated workflows, task assignment, "
            "real-time progress tracking, transparent grievance resolution. "
            "REQUIRED: complaint intake, workflow automation, task assignment, real-time tracker, "
            "transparent resolution pipeline, CRM dashboard with SLAs."
        ),
        "2H · AI Co-Pilot for Public Leaders & Administrators": (
            "Secure hardware-software intelligence assistant: summarizes documents/meetings, drafts speeches, "
            "tracks constituency data, manages schedules, provides real-time decision insights. "
            "REQUIRED: document/meeting summarization, speech drafting, constituency data module, "
            "schedule management, secure hardware component mentioned."
        ),
        "2I · Party Worker Management System": (
            "Digitally organize worker profiles, assign area-wise responsibilities, track daily outreach "
            "activities, monitor performance dashboards, enable fast communication, execute campaigns at scale. "
            "REQUIRED: worker profiles, area assignment engine, daily activity tracking, performance dashboard, "
            "in-app communication, campaign execution module."
        ),
        "2J · AI Sentiment Analysis Engine": (
            "Multi-language sentiment analysis across social media, news, surveys, ground feedback. "
            "Detects sentiment polarity and key trends; generates booth-wise + constituency-wise dashboards, heatmaps, alerts. "
            "REQUIRED: multilingual NLP, multi-source ingestion, sentiment classification, booth-level granularity, "
            "heatmap visualizations, real-time alert system."
        ),
    },
    "Domain 3 — Open Innovation": {
        "3A · Open Innovation — Healthcare": "Original tech-driven solution for a real healthcare problem.",
        "3B · Open Innovation — Robotics": "Original tech-driven solution for a real robotics problem.",
        "3C · Open Innovation — Agriculture": "Original tech-driven solution for a real agriculture problem.",
        "3D · Open Innovation — FinTech": "Original tech-driven solution for a real fintech problem.",
        "3E · Open Innovation — DeepTech": "Original tech-driven solution for a real deep-tech problem.",
        "3F · Open Innovation — Cybersecurity": "Original tech-driven solution for a real cybersecurity problem.",
        "3G · Open Innovation — Blockchain": "Original tech-driven solution for a real blockchain use-case.",
        "3H · Open Innovation — AI/ML": "Original tech-driven solution for a real AI/ML problem.",
        "3I · Open Innovation — Sustainability": "Original tech-driven solution for a real sustainability problem.",
        "3J · Open Innovation — EdTech": "Original tech-driven solution for a real EdTech problem.",
        "3K · Open Innovation — Smart Governance": "Original tech-driven solution for a real smart governance problem.",
        "3L · Open Innovation — Other": "Original tech-driven solution for any real-world problem with innovative technology.",
    },
}

ALL_DOMAINS = list(PROBLEM_STATEMENTS.keys())

SYSTEM_PROMPT = """
You are a brutally strict technical reviewer for India Innovates 2026.

Follow these rules:
1. Score only what is explicitly present in the PPT extract.
2. Treat template text, placeholders, and almost-empty slides as absent.
3. Never give benefit of doubt.
4. For alignment, compare against the exact required elements of the selected problem statement.
5. Domain mentions without technical compliance deserve 0 or 2 raw, which both map to zero final alignment score.
6. Return valid JSON only.
""".strip()


def normalize_whitespace(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def is_placeholder_text(text: str) -> bool:
    normalized = normalize_whitespace(text)
    if not normalized:
        return True
    lower = normalized.lower()
    if len(normalized) < 40:
        return True
    return any(fingerprint in lower for fingerprint in PLACEHOLDER_FINGERPRINTS)


def count_tokens(text: str, model: str) -> int:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def truncate_to_tokens(text: str, max_tokens: int, model: str) -> str:
    try:
        encoding = tiktoken.encoding_for_model(model)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    encoded = encoding.encode(text)
    if len(encoded) <= max_tokens:
        return text
    trimmed = encoding.decode(encoded[:max_tokens])
    return trimmed + "\n\n[TRUNCATED FOR TOKEN LIMIT]"


def extract_text_from_shape(shape: Any) -> list[str]:
    lines: list[str] = []

    if getattr(shape, "has_text_frame", False):
        text_frame = getattr(shape, "text_frame", None)
        if text_frame is not None:
            for paragraph in text_frame.paragraphs:
                paragraph_text = " ".join(run.text.strip() for run in paragraph.runs if run.text.strip())
                if not paragraph_text:
                    paragraph_text = paragraph.text.strip()
                if paragraph_text:
                    lines.append(paragraph_text)

    if getattr(shape, "has_table", False):
        table = getattr(shape, "table", None)
        if table is not None:
            for row in table.rows:
                cell_values = [normalize_whitespace(cell.text) for cell in row.cells if normalize_whitespace(cell.text)]
                if cell_values:
                    lines.append(" | ".join(cell_values))

    return lines


def extract_ppt_text(file_bytes: bytes) -> dict[str, Any]:
    presentation = Presentation(BytesIO(file_bytes))
    slide_entries: list[dict[str, Any]] = []

    for index, slide in enumerate(presentation.slides, start=1):
        label = SLIDE_LABELS[index - 1] if index - 1 < len(SLIDE_LABELS) else f"SLIDE_{index}"
        lines: list[str] = []
        for shape in slide.shapes:
            lines.extend(extract_text_from_shape(shape))

        slide_entries.append(
            {
                "index": index,
                "label": label,
                "text": normalize_whitespace("\n".join(lines)),
            }
        )

    slide_map = {entry["label"]: entry["text"] for entry in slide_entries}
    return {"slides": slide_entries, "slide_map": slide_map}


def extract_team_name(slide_map: dict[str, str]) -> str:
    cover_text = slide_map.get("COVER / TEAM INFO", "")
    ignored = {
        "india innovates 2026",
        "team name",
        "members name and affiliation",
        "cover / team info",
    }
    for line in cover_text.splitlines():
        candidate = line.strip(" :-")
        if candidate and candidate.lower() not in ignored:
            return candidate[:80]
    return "Unknown Team"


def build_llm_ppt_payload(slide_map: dict[str, str]) -> tuple[str, list[str], list[str]]:
    present_required: list[str] = []
    missing_required: list[str] = []
    sections: list[str] = []

    for label in REQUIRED_SLIDES:
        text = slide_map.get(label, "")
        if text and not is_placeholder_text(text):
            present_required.append(label)
            sections.append(f"[{label}]\n{text}")
        elif text:
            missing_required.append(label)
            sections.append(f"[{label}]\n<EMPTY_OR_TEMPLATE>")
        else:
            missing_required.append(label)
            sections.append(f"[{label}]\n<MISSING_SLIDE>")

    reference_text = slide_map.get("REFERENCES / LINKS", "")
    if reference_text:
        sections.append(f"[REFERENCES / LINKS]\n{reference_text}")

    return "\n\n".join(sections), present_required, missing_required


def build_eval_prompt(ppt_content: str, ps_key: str, ps_text: str) -> str:
    return f"""
PROBLEM STATEMENT SELECTED BY HUMAN REVIEWER
ID: {ps_key}
TEXT: {ps_text}

PPT CONTENT EXTRACT
{ppt_content}

Evaluate on exactly two dimensions using only these raw values:
- PPT quality: 0, 2, 4, 6, 8, 10
- Alignment: 0, 2, 4, 6, 8, 10

PPT QUALITY RUBRIC
0 = all placeholder/empty/gibberish
2 = only 1-2 slides contain real text
4 = majority filled but shallow/generic
6 = most slides meaningful but architecture weak or tech generic
8 = solid throughout with clear architecture and specific tech
10 = exceptional throughout, detailed and credible

ALIGNMENT RUBRIC
0 = wrong domain / off-topic / different problem
2 = mentions the domain but ignores the specific requirements
4 = partially addresses the problem and misses more than half of requirements
6 = addresses main thrust but misses 1-2 key requirements
8 = addresses nearly all requirements with specificity
10 = addresses every required element clearly and concretely

Return strict JSON with this exact shape:
{
  "ppt_score_raw": 0,
  "alignment_score_raw": 0,
  "ppt_verdict": "short sentence",
  "alignment_verdict": "short sentence",
  "red_flags": ["flag 1", "flag 2"]
}

No markdown. No commentary. JSON only.
""".strip()


def sanitize_raw_score(value: Any, allowed_values: tuple[int, ...]) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        return allowed_values[0]
    return candidate if candidate in allowed_values else allowed_values[0]


def compute_final_score(media_raw: int, proto_raw: int, ppt_raw: int, align_raw: int) -> dict[str, float]:
    media_score = MEDIA_SCORE_MAP.get(media_raw, 0.0)
    proto_score = PROTO_SCORE_MAP.get(proto_raw, 0.0)
    ppt_score = PPT_SCORE_MAP.get(ppt_raw, 0.0)
    align_score = ALIGN_SCORE_MAP.get(align_raw, 0.0)
    total = round(min(media_score + proto_score + ppt_score + align_score, 1.0), 4)
    return {
        "media_score": media_score,
        "proto_score": proto_score,
        "ppt_score": ppt_score,
        "align_score": align_score,
        "total": total,
    }


def default_llm_result(error_message: str) -> dict[str, Any]:
    return {
        "ppt_score_raw": 0,
        "alignment_score_raw": 0,
        "ppt_verdict": f"Evaluation failed: {error_message}",
        "alignment_verdict": "Evaluation failed.",
        "red_flags": ["EVALUATION_FAILED"],
    }


def call_openai_for_scores(user_prompt: str, api_key: str, model: str) -> dict[str, Any]:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=400,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    raw_content = response.choices[0].message.content
    if not raw_content:
        raise ValueError("Model returned empty content.")
    parsed = json.loads(raw_content)
    parsed["ppt_score_raw"] = sanitize_raw_score(parsed.get("ppt_score_raw"), ALLOWED_PPT_RAW)
    parsed["alignment_score_raw"] = sanitize_raw_score(parsed.get("alignment_score_raw"), ALLOWED_ALIGN_RAW)
    if not isinstance(parsed.get("ppt_verdict"), str):
        parsed["ppt_verdict"] = "No PPT verdict returned."
    if not isinstance(parsed.get("alignment_verdict"), str):
        parsed["alignment_verdict"] = "No alignment verdict returned."
    if not isinstance(parsed.get("red_flags"), list):
        parsed["red_flags"] = []
    parsed["red_flags"] = [str(flag)[:120] for flag in parsed["red_flags"][:6]]
    return parsed


def safe_call_openai(user_prompt: str, api_key: str, model: str) -> dict[str, Any]:
    for attempt in range(3):
        try:
            return call_openai_for_scores(user_prompt, api_key, model)
        except RateLimitError:
            if attempt == 2:
                return default_llm_result("Rate limit hit after 3 attempts.")
            time.sleep(8 * (attempt + 1))
        except (APIError, json.JSONDecodeError, ValueError) as exc:
            if attempt == 2:
                return default_llm_result(str(exc))
            time.sleep(2 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001
            return default_llm_result(str(exc))
    return default_llm_result("Unknown failure.")


def ensure_submission_defaults(existing: dict[str, Any] | None, file_bytes: bytes) -> dict[str, Any]:
    extracted = extract_ppt_text(file_bytes)
    slide_map = extracted["slide_map"]
    team_name = extract_team_name(slide_map)
    default_domain = ALL_DOMAINS[0]
    default_ps_key = list(PROBLEM_STATEMENTS[default_domain].keys())[0]

    base = {
        "file_bytes": file_bytes,
        "team_name": team_name,
        "domain": default_domain,
        "ps_key": default_ps_key,
        "media_link": "",
        "prototype_link": "",
        "github_link": "",
        "media_rating": 0,
        "proto_rating": 0,
        "slide_map": slide_map,
        "slides": extracted["slides"],
        "ppt_payload": None,
        "present_required": [],
        "missing_required": [],
        "llm_result": None,
    }

    if existing is None:
        base["ppt_payload"], base["present_required"], base["missing_required"] = build_llm_ppt_payload(slide_map)
        return base

    merged = {**base, **existing}
    merged["file_bytes"] = file_bytes
    merged["slide_map"] = slide_map
    merged["slides"] = extracted["slides"]
    if not merged.get("team_name") or merged["team_name"] == "Unknown Team":
        merged["team_name"] = team_name
    merged["ppt_payload"], merged["present_required"], merged["missing_required"] = build_llm_ppt_payload(slide_map)
    return merged


def refresh_extraction(submission: dict[str, Any]) -> None:
    extracted = extract_ppt_text(submission["file_bytes"])
    submission["slide_map"] = extracted["slide_map"]
    submission["slides"] = extracted["slides"]
    submission["ppt_payload"], submission["present_required"], submission["missing_required"] = build_llm_ppt_payload(
        submission["slide_map"]
    )
    if not submission.get("team_name") or submission["team_name"] == "Unknown Team":
        submission["team_name"] = extract_team_name(submission["slide_map"])


def render_slide_preview(submission: dict[str, Any], file_name: str) -> None:
    preview_lines: list[str] = []
    for slide in submission.get("slides", []):
        slide_text = slide.get("text", "") or "<EMPTY>"
        preview_lines.append(f"[{slide['index']}] {slide['label']}\n{slide_text}")
    st.text_area(
        "Extracted PPT text",
        value="\n\n".join(preview_lines),
        key=f"preview_{file_name}",
        height=260,
        disabled=True,
    )


def make_result_row(file_name: str, submission: dict[str, Any], llm_result: dict[str, Any]) -> dict[str, Any]:
    ppt_raw = sanitize_raw_score(llm_result.get("ppt_score_raw"), ALLOWED_PPT_RAW)
    align_raw = sanitize_raw_score(llm_result.get("alignment_score_raw"), ALLOWED_ALIGN_RAW)
    scores = compute_final_score(submission["media_rating"], submission["proto_rating"], ppt_raw, align_raw)
    verdict = "IN" if scores["total"] >= IN_THRESHOLD else "OUT"

    local_flags = list(llm_result.get("red_flags", []))
    if submission.get("missing_required"):
        local_flags.append("MISSING_REQUIRED_SLIDES")
    if submission["proto_rating"] == 0:
        local_flags.append("NO_WORKING_PROTO_OR_GITHUB")

    deduped_flags = list(dict.fromkeys(flag for flag in local_flags if flag))

    return {
        "File": file_name,
        "Team": submission.get("team_name", ""),
        "Domain": submission.get("domain", ""),
        "Problem Statement": submission.get("ps_key", ""),
        "Media Link": submission.get("media_link", ""),
        "Prototype Link": submission.get("prototype_link", ""),
        "GitHub Link": submission.get("github_link", ""),
        "Media Raw": submission.get("media_rating", 0),
        "Media Score": scores["media_score"],
        "Prototype Raw": submission.get("proto_rating", 0),
        "Prototype Score": scores["proto_score"],
        "PPT Raw": ppt_raw,
        "PPT Score": scores["ppt_score"],
        "Alignment Raw": align_raw,
        "Alignment Score": scores["align_score"],
        "TOTAL": scores["total"],
        "VERDICT": verdict,
        "Present Required Slides": " | ".join(submission.get("present_required", [])),
        "Missing Required Slides": " | ".join(submission.get("missing_required", [])),
        "PPT Verdict": llm_result.get("ppt_verdict", ""),
        "Alignment Verdict": llm_result.get("alignment_verdict", ""),
        "Red Flags": " | ".join(deduped_flags),
    }


def make_auto_out_result_row(file_name: str, submission: dict[str, Any]) -> dict[str, Any]:
    media_score = MEDIA_SCORE_MAP.get(submission.get("media_rating", 0), 0.0)
    return {
        "File": file_name,
        "Team": submission.get("team_name", ""),
        "Domain": submission.get("domain", ""),
        "Problem Statement": submission.get("ps_key", ""),
        "Media Link": submission.get("media_link", ""),
        "Prototype Link": submission.get("prototype_link", ""),
        "GitHub Link": submission.get("github_link", ""),
        "Media Raw": submission.get("media_rating", 0),
        "Media Score": media_score,
        "Prototype Raw": 0,
        "Prototype Score": 0.0,
        "PPT Raw": "SKIPPED",
        "PPT Score": 0.0,
        "Alignment Raw": "SKIPPED",
        "Alignment Score": 0.0,
        "TOTAL": 0.0,
        "VERDICT": "AUTO-OUT",
        "Present Required Slides": " | ".join(submission.get("present_required", [])),
        "Missing Required Slides": " | ".join(submission.get("missing_required", [])),
        "PPT Verdict": "Skipped because Prototype + GitHub rating is 0.",
        "Alignment Verdict": "Skipped because Prototype + GitHub rating is 0.",
        "Red Flags": "PROTO_GH_HARD_GATE_FAILED",
    }


st.set_page_config(page_title="India Innovates 2026 Evaluator", page_icon="🇮🇳", layout="wide")

for key, default in (("submissions", {}), ("results", [])):
    if key not in st.session_state:
        st.session_state[key] = default

with st.sidebar:
    st.markdown("## India Innovates 2026")
    st.markdown("Batch screening evaluator")
    st.divider()

    api_key = st.text_input("OpenAI API key", type="password", placeholder="sk-...")
    model_choice = st.selectbox("Model", options=["gpt-4o", "gpt-4o-mini"], index=0)

    st.divider()
    st.markdown("### Marking scheme in use")
    st.caption("Using the current per-question score tables and hard-gate rule from the scheme file.")
    st.markdown(
        """
| Component | Raw values | Final score |
|---|---|---|
| Media | 0 / 1 / 5 | 0.00 / 0.10 / 0.25 |
| Prototype + GitHub | 0 / 1 / 5 | 0.00 / 0.10 / 0.35 |
| PPT Quality | 0 / 2 / 4 / 6 / 8 / 10 | 0.00 / 0.06 / 0.12 / 0.18 / 0.24 / 0.30 |
| PS Alignment | 0 / 2 / 4 / 6 / 8 / 10 | 0.00 / 0.00 / 0.10 / 0.18 / 0.28 / 0.35 |

**Hard gate:** Prototype + GitHub rating `0` → auto-OUT, skip LLM  
**IN threshold:** 0.60  
**Total cap:** 1.00
        """
    )

st.title("🇮🇳 India Innovates 2026 — Screening Evaluator")
st.caption("Upload PPTs, fill human review inputs, run LLM scoring, then export CSV.")

st.header("Step 1 · Upload PPT batch", divider="gray")
uploaded_files = st.file_uploader(
    f"Upload up to {MAX_FILES_BATCH} PPTX files",
    type=["pptx"],
    accept_multiple_files=True,
)

if not uploaded_files:
    st.info("Upload one or more .pptx submissions to begin.")
    st.markdown(
        """
1. Upload PPT submissions.
2. Confirm team, domain, and problem statement.
3. Add human-reviewed media / prototype / GitHub inputs.
4. Run evaluation.
5. Export the results CSV.
        """
    )
    st.stop()

if len(uploaded_files) > MAX_FILES_BATCH:
    st.error(f"Maximum batch size is {MAX_FILES_BATCH}. You uploaded {len(uploaded_files)} files.")
    st.stop()

current_files = {uploaded_file.name for uploaded_file in uploaded_files}
for stale_name in list(st.session_state.submissions.keys()):
    if stale_name not in current_files:
        del st.session_state.submissions[stale_name]

for uploaded_file in uploaded_files:
    raw_bytes = uploaded_file.getvalue()
    existing = st.session_state.submissions.get(uploaded_file.name)
    try:
        st.session_state.submissions[uploaded_file.name] = ensure_submission_defaults(existing, raw_bytes)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to read {uploaded_file.name}: {exc}")

st.header("Step 2 · Human review inputs", divider="gray")
st.info(
    "Match the exact problem statement claimed by the team. Media is optional bonus. Prototype + GitHub rating 0 triggers auto-OUT and skips LLM evaluation."
)

for uploaded_file in uploaded_files:
    file_name = uploaded_file.name
    submission = st.session_state.submissions[file_name]

    with st.expander(f"{file_name} · Team: {submission['team_name']}", expanded=True):
        submission["team_name"] = st.text_input(
            "Team name",
            value=submission["team_name"],
            key=f"team_{file_name}",
        )

        left_col, right_col = st.columns([1.2, 1])

        with left_col:
            current_domain = submission["domain"] if submission["domain"] in ALL_DOMAINS else ALL_DOMAINS[0]
            selected_domain = st.selectbox(
                "Domain",
                options=ALL_DOMAINS,
                index=ALL_DOMAINS.index(current_domain),
                key=f"domain_{file_name}",
            )
            submission["domain"] = selected_domain

            ps_options = list(PROBLEM_STATEMENTS[selected_domain].keys())
            if submission["ps_key"] not in ps_options:
                submission["ps_key"] = ps_options[0]

            submission["ps_key"] = st.selectbox(
                "Problem statement",
                options=ps_options,
                index=ps_options.index(submission["ps_key"]),
                key=f"ps_{file_name}",
            )

            with st.expander("Problem statement requirements", expanded=False):
                st.write(PROBLEM_STATEMENTS[selected_domain][submission["ps_key"]])

        with right_col:
            submission["media_link"] = st.text_input(
                "Media link (optional)",
                value=submission.get("media_link", ""),
                key=f"media_link_{file_name}",
                placeholder="Video / demo / audio link",
            )
            submission["prototype_link"] = st.text_input(
                "Prototype link",
                value=submission.get("prototype_link", ""),
                key=f"prototype_link_{file_name}",
                placeholder="Live prototype or deployment link",
            )
            submission["github_link"] = st.text_input(
                "GitHub repo link",
                value=submission.get("github_link", ""),
                key=f"github_link_{file_name}",
                placeholder="Repository URL",
            )

        rating_col_1, rating_col_2 = st.columns(2)
        with rating_col_1:
            submission["media_rating"] = st.radio(
                "Media rating",
                options=[0, 1, 5],
                horizontal=True,
                key=f"media_rating_{file_name}",
                index=[0, 1, 5].index(submission["media_rating"]),
                format_func=lambda value: {0: "0 · Not submitted", 1: "1 · Weak", 5: "5 · Strong"}[value],
            )
        with rating_col_2:
            submission["proto_rating"] = st.radio(
                "Prototype + GitHub rating",
                options=[0, 1, 5],
                horizontal=True,
                key=f"proto_rating_{file_name}",
                index=[0, 1, 5].index(submission["proto_rating"]),
                format_func=lambda value: {0: "0 · Missing", 1: "1 · Weak", 5: "5 · Strong"}[value],
            )

        action_col, status_col = st.columns([1, 2])
        with action_col:
            if st.button("Refresh PPT extraction", key=f"refresh_{file_name}"):
                try:
                    refresh_extraction(submission)
                    st.success("PPT text refreshed.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Extraction failed: {exc}")

        with status_col:
            token_count = count_tokens(submission.get("ppt_payload", ""), model_choice)
            required_present = len(submission.get("present_required", []))
            required_missing = len(submission.get("missing_required", []))
            st.caption(
                f"Required slides present: {required_present}/5 · Missing/template: {required_missing} · "
                f"Prompt payload tokens: {token_count}/{MAX_PPT_TOKENS}"
            )

        with st.expander("Extracted PPT preview", expanded=False):
            render_slide_preview(submission, file_name)

        if submission.get("llm_result"):
            if submission.get("proto_rating", 0) == 0:
                last_result = make_auto_out_result_row(file_name, submission)
            else:
                last_result = make_result_row(file_name, submission, submission["llm_result"])
            st.markdown(
                f"**Last score:** total **{last_result['TOTAL']:.2f}** → "
                f"{'✅ IN' if last_result['VERDICT'] == 'IN' else '❌ ' + last_result['VERDICT']}"
            )
            st.caption(
                f"Media {last_result['Media Score']:.2f} · Prototype {last_result['Prototype Score']:.2f} · "
                f"PPT {last_result['PPT Score']:.2f} · Alignment {last_result['Alignment Score']:.2f}"
            )

st.header("Step 3 · Run LLM evaluation", divider="gray")
if not api_key:
    st.warning("Enter the OpenAI API key in the sidebar to evaluate submissions.")
else:
    trigger = st.button("Evaluate all submissions", type="primary", use_container_width=True)
    st.caption(
        f"Batch size: {len(st.session_state.submissions)} · Model: {model_choice} · "
        f"PPT token budget per submission: {MAX_PPT_TOKENS}"
    )

    if trigger:
        st.session_state.results = []
        progress = st.progress(0, text="Preparing evaluations...")
        status_box = st.empty()

        items = list(st.session_state.submissions.items())
        for index, (file_name, submission) in enumerate(items, start=1):
            status_box.info(f"Evaluating {index}/{len(items)}: {file_name}")

            if not submission.get("ppt_payload"):
                refresh_extraction(submission)

            if submission.get("proto_rating", 0) == 0:
                submission["llm_result"] = {
                    "ppt_score_raw": "SKIPPED",
                    "alignment_score_raw": "SKIPPED",
                    "ppt_verdict": "Skipped because Prototype + GitHub rating is 0.",
                    "alignment_verdict": "Skipped because Prototype + GitHub rating is 0.",
                    "red_flags": ["PROTO_GH_HARD_GATE_FAILED"],
                }
                st.session_state.results.append(make_auto_out_result_row(file_name, submission))
                progress.progress(index / len(items), text=f"Completed {index}/{len(items)}")
                time.sleep(0.1)
                continue

            domain = submission["domain"]
            ps_key = submission["ps_key"]
            ps_text = PROBLEM_STATEMENTS[domain][ps_key]

            truncated_payload = truncate_to_tokens(submission["ppt_payload"], MAX_PPT_TOKENS, model_choice)
            prompt = build_eval_prompt(truncated_payload, ps_key, ps_text)

            if count_tokens(SYSTEM_PROMPT + "\n\n" + prompt, model_choice) > LLM_CONTEXT_SOFT_LIMIT:
                trimmed_budget = max(800, MAX_PPT_TOKENS - 800)
                prompt = build_eval_prompt(
                    truncate_to_tokens(submission["ppt_payload"], trimmed_budget, model_choice),
                    ps_key,
                    ps_text,
                )

            llm_result = safe_call_openai(prompt, api_key, model_choice)
            submission["llm_result"] = llm_result
            st.session_state.results.append(make_result_row(file_name, submission, llm_result))

            progress.progress(index / len(items), text=f"Completed {index}/{len(items)}")
            time.sleep(0.2)

        status_box.success("Batch evaluation complete.")

if st.session_state.results:
    st.header("Step 4 · Results", divider="gray")
    results_df = pd.DataFrame(st.session_state.results)

    total_evaluated = len(results_df)
    total_in = int((results_df["VERDICT"] == "IN").sum())
    total_out = int(results_df["VERDICT"].isin(["OUT", "AUTO-OUT"]).sum())
    avg_total = float(results_df["TOTAL"].mean()) if total_evaluated else 0.0

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Evaluated", total_evaluated)
    metric_2.metric("IN", total_in)
    metric_3.metric("OUT", total_out)
    metric_4.metric("Average total", f"{avg_total:.2f}")

    st.dataframe(results_df, use_container_width=True, hide_index=True)

    with st.expander("Detailed verdicts", expanded=False):
        for row in st.session_state.results:
            icon = "✅" if row["VERDICT"] == "IN" else "❌"
            st.markdown(f"**{icon} {row['Team']}** — {row['File']}")
            st.write(
                f"Total: {row['TOTAL']:.2f} | Media: {row['Media Score']:.2f} | "
                f"Prototype: {row['Prototype Score']:.2f} | PPT: {row['PPT Score']:.2f} | "
                f"Alignment: {row['Alignment Score']:.2f}"
            )
            st.caption(f"Verdict: {row['VERDICT']}")
            st.caption(f"PPT: {row['PPT Verdict']}")
            st.caption(f"Alignment: {row['Alignment Verdict']}")
            if row["Red Flags"]:
                st.caption(f"Flags: {row['Red Flags']}")
            st.divider()

    csv_bytes = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download results CSV",
        data=csv_bytes,
        file_name=f"ii2026_results_{int(time.time())}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    if st.button("Clear batch", use_container_width=True):
        st.session_state.submissions = {}
        st.session_state.results = []
        st.rerun()
