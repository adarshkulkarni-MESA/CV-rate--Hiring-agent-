"""Scores a redacted CV against the Kargo rubric, using Gemini.

Falls back to a transparent, clearly-labeled mock scorer when no
GEMINI_API_KEY is set, so the pipeline can be exercised end to end before
a real key is wired in. The mock is a rough keyword heuristic — it exists to
prove the plumbing works, never to actually rank real candidates.
"""
import json
import os
from pathlib import Path

RUBRIC_PATH = Path(__file__).parent.parent / "prompts" / "scoring_rubric.md"
JDS_PATH = Path(__file__).parent.parent / "data" / "job_descriptions.json"

INTERVIEW_THRESHOLD = 6.0

LOGISTICS_KEYWORDS = [
    "freight", "forwarder", "shipment", "carrier", "customs", "cha ",
    "3pl", "logistics", "port", "jnpt", "bill of lading", "dgft",
    "supply chain", "nvocc", "container", "vessel", "shipping line",
]
OWNERSHIP_KEYWORDS = [
    "built", "redesigned", "independently", "no committee", "killed",
    "post-mortem", "post mortem", "owned", "sole", "from scratch",
]


def score_candidate(redacted_cv: str, role: str) -> dict:
    """role is 'pm' or 'spm'."""
    role = role.lower()
    if role not in ("pm", "spm"):
        raise ValueError("role must be 'pm' or 'spm'")

    if os.environ.get("GEMINI_API_KEY"):
        return _score_with_gemini(redacted_cv, role)
    return _mock_score(redacted_cv, role)


def _score_with_gemini(redacted_cv: str, role: str) -> dict:
    import google.generativeai as genai

    api_key = os.environ["GEMINI_API_KEY"]
    genai.configure(api_key=api_key)

    rubric = RUBRIC_PATH.read_text(encoding="utf-8")
    jds = json.loads(JDS_PATH.read_text(encoding="utf-8"))
    jd = jds[role]

    system = (
        rubric
        + "\n\n## Job description for this role\n\n"
        + json.dumps(jd, indent=2)
        + "\n\nReturn ONLY the JSON object described above. No prose outside the JSON."
    )

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
        ),
    )

    prompt = f"Score this redacted CV for the {jd['title']} role:\n\n{redacted_cv}"
    response = model.generate_content(prompt)
    raw = response.text
    return json.loads(raw)


def _mock_score(redacted_cv: str, role: str) -> dict:
    """Rule-based stand-in. NOT the real rubric — see module docstring."""
    text = redacted_cv.lower()

    ops_hits = sum(1 for k in LOGISTICS_KEYWORDS if k in text)
    dim1 = min(10, ops_hits * 2.5)

    own_hits = sum(1 for k in OWNERSHIP_KEYWORDS if k in text)
    dim2 = min(10, own_hits * 2.0)

    dim3 = 6.0  # neutral placeholder — real scoring needs the LLM to read the JD against experience
    dim4 = 6.0 if len(text) > 800 else 3.0  # crude proxy for detail/specificity

    total = round(0.40 * dim1 + 0.25 * dim2 + 0.20 * dim3 + 0.15 * dim4, 1)
    recommendation = "interview" if total >= INTERVIEW_THRESHOLD else "reject"

    return {
        "dim1_ops_exposure": {"score": dim1, "evidence": f"[MOCK] {ops_hits} logistics-keyword hits"},
        "dim2_ownership": {"score": dim2, "evidence": f"[MOCK] {own_hits} ownership-keyword hits"},
        "dim3_role_fit": {"score": dim3, "evidence": "[MOCK] placeholder — needs the real model to read years/JD fit"},
        "dim4_communication": {"score": dim4, "evidence": "[MOCK] length-based proxy only"},
        "total_score": total,
        "recommendation": recommendation,
        "interview_brief": "[MOCK MODE] Set GEMINI_API_KEY for a real interview brief.",
        "email_subject": f"Your application to Kargo ({role.upper()})",
        "email_body": "[MOCK MODE] Set GEMINI_API_KEY for a real drafted email.",
    }
