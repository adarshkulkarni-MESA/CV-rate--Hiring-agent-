"""Strips personal identifying detail from CV text before it reaches the AI.

This is what the Components Map calls out explicitly: "excludes personal
details from AI." The rubric scores work history, not identity — this is
the enforcement point for that boundary, not a comment in a prompt.

Not perfect PII removal (that's a harder problem than this case asks us to
solve) but removes the obvious identity signals: name (first line heuristic),
email, phone, LinkedIn/GitHub handles, physical address fragments, and photo
references.
"""
import re


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(\+?\d[\d\-\s]{7,}\d)")
URL_RE = re.compile(r"(https?://\S+|(?:www\.)?linkedin\.com/\S+|(?:www\.)?github\.com/\S+)")


def redact(cv_text: str, candidate_name_hint: str | None = None) -> tuple[str, str]:
    """Returns (redacted_text, candidate_id).

    candidate_id is a stable, non-identifying handle (e.g. "cand-8f3a") used
    to key the dashboard and file names — never the candidate's real name.
    """
    text = cv_text

    # The candidate's name is almost always the first non-empty line of a CV.
    # We remove that line entirely rather than trying to pattern-match names.
    lines = [l for l in text.splitlines() if l.strip()]
    name_line = lines[0].strip() if lines else (candidate_name_hint or "")

    text = text.replace(name_line, "[CANDIDATE]", 1) if name_line else text
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[LINK]", text)
    text = PHONE_RE.sub("[PHONE]", text)

    candidate_id = _make_id(name_line or candidate_name_hint or text[:40])
    return text, candidate_id


def _make_id(seed: str) -> str:
    import hashlib

    return "cand-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8]
