"""Supabase persistence layer.

Writes one row per scored candidate to the `candidates` table. Also exposes
a helper to flip email_sent=true when the send command completes. Falls back
gracefully (prints a warning) when SUPABASE_URL / SUPABASE_KEY are not set,
so the pipeline still works with CSV-only output during local dev.
"""
import os

SUPABASE_URL = os.environ.get(
    "SUPABASE_URL", "https://tsgvfaiojilehdhpjrqj.supabase.co"
)
SUPABASE_KEY = os.environ.get(
    "SUPABASE_KEY",
    "sb_publishable_R5AfVhY3BRfN-Wf0VXJlKA_nyI4_bQn",
)


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


def list_candidates(role: str | None = None) -> list[dict]:
    """Return all candidates, optionally filtered by role, newest first."""
    try:
        q = _client().table("candidates").select("*").order("scored_at", desc=True)
        if role:
            q = q.eq("role", role)
        return q.execute().data
    except Exception as exc:
        print(f"[db] warning: could not query Supabase — {exc}")
        return []
