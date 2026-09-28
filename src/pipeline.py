"""CLI: score, score-batch, score-from-github, send, list.

Trigger -> Input -> Context -> Processing -> AI -> Output, as one command per
CV (score) or one command per folder/GitHub path (score-batch / score-from-github),
writing into a shared dashboard and Supabase. `send` is the one command that
talks to Resend, and it sends only a draft that already exists on disk for
that candidate.
"""
import argparse
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from cv_parser import parse_cv
from redact import redact, EMAIL_RE
from scorer import score_candidate
from emailer import send_email
from db import upsert_candidate, mark_email_sent, list_candidates

BASE = Path(__file__).parent.parent
OUTPUT_DIR = BASE / "output"
DASHBOARD_CSV = BASE / "dashboard.csv"
CONTACTS_JSON = BASE / "output" / ".contacts.json"

DASHBOARD_FIELDS = [
    "candidate_id", "role", "total_score", "recommendation",
    "dim1_ops_exposure", "dim2_ownership", "dim3_role_fit", "dim4_communication",
    "source_file",
]


def cmd_score(cv_path: str, role: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    raw_text = parse_cv(cv_path)

    contact_match = EMAIL_RE.search(raw_text)
    real_email = contact_match.group(0) if contact_match else None

    redacted_text, candidate_id = redact(raw_text)
    result = score_candidate(redacted_text, role)

    _save_contact(candidate_id, real_email)
    _write_outputs(candidate_id, role, cv_path, result)
    _append_dashboard_row(candidate_id, role, cv_path, result)
    upsert_candidate(candidate_id, role, cv_path, result)

    print(f"[{candidate_id}] {role.upper()} score={result['total_score']} "
          f"-> {result['recommendation']}  (draft in output/{candidate_id}_email.md)")


def cmd_score_batch(directory: str, role: str) -> None:
    cv_dir = Path(directory)
    files = sorted([p for p in cv_dir.iterdir() if p.suffix.lower() in (".docx", ".pdf", ".txt")])
    if not files:
        print(f"No CV files found in {directory}")
        return
    for f in files:
        try:
            cmd_score(str(f), role)
        except Exception as e:
            print(f"[skip] {f.name}: {e}")


def cmd_score_from_github(repo: str, path: str, role: str, ref: str) -> None:
    """Fetch CVs from a GitHub repo path and score them all."""
    from github_source import fetch_cvs_from_github

    print(f"[github] fetching CVs from {repo}/{path} at ref={ref} ...")
    local_files = fetch_cvs_from_github(repo, path, ref)
    if not local_files:
        return
    for f in local_files:
        try:
            cmd_score(f, role)
        except Exception as e:
            print(f"[skip] {Path(f).name}: {e}")


def cmd_send(candidate_id: str) -> None:
    email_path = OUTPUT_DIR / f"{candidate_id}_email.md"
    if not email_path.exists():
        raise SystemExit(f"No draft found for {candidate_id}. Run `score` first.")

    subject, body = _read_draft(email_path)
    to_address = _load_contact(candidate_id)
    if not to_address:
        raise SystemExit(
            f"No contact email on file for {candidate_id} — cannot send. "
            "This should not happen if `score` ran on this candidate."
        )

    confirm = input(
        f"About to send to {to_address}:\n  Subject: {subject}\n"
        f"Send exactly this draft now? [y/N] "
    )
    if confirm.strip().lower() != "y":
        print("Not sent.")
        return

    result = send_email(to_address, subject, body)
    mark_email_sent(candidate_id)
    print(f"Sent. Resend id: {result.get('id')}")


def cmd_list(role: str | None = None) -> None:
    """Print the dashboard from Supabase, newest first."""
    rows = list_candidates(role)
    if not rows:
        print("No candidates scored yet.")
        return
    header = f"{'ID':<16}  {'Role':<4}  {'Score':<6}  {'Rec':<9}  {'Sent':<5}  Source"
    print(header)
    print("-" * len(header))
    for r in rows:
        sent = "yes" if r.get("email_sent") else "no"
        src = Path(r.get("source_file") or "").name or "—"
        print(f"{r['candidate_id']:<16}  {r['role']:<4}  {r['total_score']:<6}  "
              f"{r['recommendation']:<9}  {sent:<5}  {src}")


def _write_outputs(candidate_id: str, role: str, source_file: str, result: dict) -> None:
    brief_path = OUTPUT_DIR / f"{candidate_id}_brief.md"
    brief_path.write_text(
        f"# Interview brief — {candidate_id} ({role.upper()})\n\n"
        f"Source: {source_file}\n\n"
        f"Total score: {result['total_score']}/10  ->  {result['recommendation']}\n\n"
        f"## Why this ranking\n\n"
        f"- Ground-level ops exposure ({result['dim1_ops_exposure']['score']}/10): "
        f"{result['dim1_ops_exposure']['evidence']}\n"
        f"- Ownership under ambiguity ({result['dim2_ownership']['score']}/10): "
        f"{result['dim2_ownership']['evidence']}\n"
        f"- Role-fit ({result['dim3_role_fit']['score']}/10): "
        f"{result['dim3_role_fit']['evidence']}\n"
        f"- Communication ({result['dim4_communication']['score']}/10): "
        f"{result['dim4_communication']['evidence']}\n\n"
        f"## What to probe if this goes to interview\n\n"
        f"{result['interview_brief']}\n",
        encoding="utf-8",
    )

    email_path = OUTPUT_DIR / f"{candidate_id}_email.md"
    email_path.write_text(
        f"Subject: {result['email_subject']}\n\n{result['email_body']}\n",
        encoding="utf-8",
    )


def _read_draft(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"Subject:\s*(.*)\n\n(.*)", text, re.S)
    if not m:
        raise SystemExit(f"Malformed draft file: {path}")
    return m.group(1).strip(), m.group(2).strip()


def _append_dashboard_row(candidate_id: str, role: str, source_file: str, result: dict) -> None:
    is_new = not DASHBOARD_CSV.exists()
    with DASHBOARD_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=DASHBOARD_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow({
            "candidate_id": candidate_id,
            "role": role,
            "total_score": result["total_score"],
            "recommendation": result["recommendation"],
            "dim1_ops_exposure": result["dim1_ops_exposure"]["score"],
            "dim2_ownership": result["dim2_ownership"]["score"],
            "dim3_role_fit": result["dim3_role_fit"]["score"],
            "dim4_communication": result["dim4_communication"]["score"],
            "source_file": source_file,
        })


def _save_contact(candidate_id: str, email: str | None) -> None:
    contacts = _load_contacts()
    contacts[candidate_id] = email
    CONTACTS_JSON.parent.mkdir(exist_ok=True)
    CONTACTS_JSON.write_text(json.dumps(contacts, indent=2), encoding="utf-8")


def _load_contact(candidate_id: str) -> str | None:
    return _load_contacts().get(candidate_id)


def _load_contacts() -> dict:
    if CONTACTS_JSON.exists():
        return json.loads(CONTACTS_JSON.read_text(encoding="utf-8"))
    return {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Kargo hiring agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_score = sub.add_parser("score", help="Score one CV")
    p_score.add_argument("--cv", required=True)
    p_score.add_argument("--role", required=True, choices=["pm", "spm"])

    p_batch = sub.add_parser("score-batch", help="Score every CV in a folder")
    p_batch.add_argument("--dir", required=True)
    p_batch.add_argument("--role", required=True, choices=["pm", "spm"])

    p_gh = sub.add_parser("score-from-github", help="Fetch CVs from a GitHub repo and score them")
    p_gh.add_argument("--repo", required=True, help="owner/repo")
    p_gh.add_argument("--path", default="", help="Directory inside the repo (default: root)")
    p_gh.add_argument("--role", required=True, choices=["pm", "spm"])
    p_gh.add_argument("--ref", default="main", help="Branch, tag, or commit (default: main)")

    p_send = sub.add_parser("send", help="Send the drafted email for one candidate")
    p_send.add_argument("--candidate-id", required=True)

    p_list = sub.add_parser("list", help="Print all scored candidates from Supabase")
    p_list.add_argument("--role", choices=["pm", "spm"], default=None)

    args = parser.parse_args()
    if args.command == "score":
        cmd_score(args.cv, args.role)
    elif args.command == "score-batch":
        cmd_score_batch(args.dir, args.role)
    elif args.command == "score-from-github":
        cmd_score_from_github(args.repo, args.path, args.role, args.ref)
    elif args.command == "send":
        cmd_send(args.candidate_id)
    elif args.command == "list":
        cmd_list(args.role)


if __name__ == "__main__":
    main()
