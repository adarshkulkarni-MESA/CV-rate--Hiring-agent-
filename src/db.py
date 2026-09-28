"""Supabase persistence layer.

Writes one row per scored candidate to the `candidates` table. Also exposes
a helper to flip email_sent=true when the send command completes. Falls back
gracefully (prints a warning) when SUPABASE_URL / SUPABASE_KEY are not set,
so the pipeline still works with CSV-only output during local dev.
"""
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")


def _client():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_candidate(candidate_id: str, role: str, source_file: str, result: dict) -> None:
    """Insert or update the scoring result for a candidate."""
    row = {
        "candidate_id": candidate_id,
        "role": role,
        "total_score": result["total_score"],
        "recommendation": result["recommendation"],
        "dim1_ops_exposure": result["dim1_ops_exposure"]["score"],
        "dim2_ownership": result["dim2_ownership"]["score"],
        "dim3_role_fit": result["dim3_role_fit"]["score"],
        "dim4_communication": result["dim4_communication"]["score"],
        "dim1_evidence": result["dim1_ops_exposure"]["evidence"],
        "dim2_evidence": result["dim2_ownership"]["evidence"],
        "dim3_evidence": result["dim3_role_fit"]["evidence"],
        "dim4_evidence": result["dim4_communication"]["evidence"],
        "interview_brief": result.get("interview_brief"),
        "email_subject": result.get("email_subject"),
        "email_body": result.get("email_body"),
        "source_file": source_file,
    }
    try:
        _client().table("candidates").upsert(row, on_conflict="candidate_id").execute()
    except Exception as exc:
        print(f"[db] warning: could not write to Supabase — {exc}")


def mark_email_sent(candidate_id: str) -> None:
    """Flip email_sent=true after the send command confirms dispatch."""
    try:
        _client().table("candidates").update({"email_sent": True}).eq(
            "candidate_id", candidate_id
        ).execute()
    except Exception as exc:
        print(f"[db] warning: could not update email_sent — {exc}")


def get_candidate(candidate_id: str) -> dict | None:
    """Return a single candidate by candidate_id, or None if not found.
    Falls back to output files when Supabase is unavailable.
    """
    try:
        rows = (
            _client()
            .table("candidates")
            .select("*")
            .eq("candidate_id", candidate_id)
            .limit(1)
            .execute()
            .data
        )
        return rows[0] if rows else None
    except Exception as exc:
        print(f"[db] warning: could not query Supabase — {exc}")

    # Fallback: reconstruct from dashboard.csv + output files
    for row in _list_from_csv():
        if row["candidate_id"] == candidate_id:
            _enrich_from_output(row, candidate_id)
            return row
    return None


def _enrich_from_output(row: dict, candidate_id: str) -> None:
    """Add email subject/body/evidence from output files if available."""
    from pathlib import Path

    out = Path(__file__).parent.parent / "output"
    email_path = out / f"{candidate_id}_email.md"
    if email_path.exists():
        text = email_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        subject_line = next((l for l in lines if l.startswith("Subject:")), "")
        row["email_subject"] = subject_line.removeprefix("Subject:").strip()
        body_start = next((i for i, l in enumerate(lines) if l.startswith("Subject:")), -1)
        row["email_body"] = "\n".join(lines[body_start + 2:]).strip() if body_start >= 0 else ""


def list_candidates(role: str | None = None) -> list[dict]:
    """Return all candidates, optionally filtered by role, newest first.
    Falls back to dashboard.csv when Supabase is unavailable.
    """
    try:
        q = _client().table("candidates").select("*").order("scored_at", desc=True)
        if role:
            q = q.eq("role", role)
        return q.execute().data
    except Exception as exc:
        print(f"[db] warning: could not query Supabase — {exc}")
        return _list_from_csv(role)


def _list_from_csv(role: str | None = None) -> list[dict]:
    """Read candidates from dashboard.csv as a fallback."""
    import csv
    from pathlib import Path

    csv_path = Path(__file__).parent.parent / "dashboard.csv"
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if role and r.get("role") != role:
                continue
            rows.append({
                "candidate_id": r.get("candidate_id", ""),
                "role": r.get("role", ""),
                "total_score": float(r.get("total_score", 0)),
                "recommendation": r.get("recommendation", ""),
                "dim1_ops_exposure": float(r.get("dim1_ops_exposure", 0)),
                "dim2_ownership": float(r.get("dim2_ownership", 0)),
                "dim3_role_fit": float(r.get("dim3_role_fit", 0)),
                "dim4_communication": float(r.get("dim4_communication", 0)),
                "source_file": r.get("source_file", ""),
                "email_sent": False,
                "email_subject": "",
                "email_body": "",
                "dim1_evidence": "",
                "dim2_evidence": "",
                "dim3_evidence": "",
                "dim4_evidence": "",
                "interview_brief": "",
            })
    return list(reversed(rows))
