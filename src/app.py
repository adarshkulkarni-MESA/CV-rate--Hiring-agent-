"""Flask web app for the Kargo Hiring Agent dashboard."""
import os
import sys
import tempfile
import re
from pathlib import Path

from flask import Flask, render_template, request, redirect, url_for, flash

sys.path.insert(0, str(Path(__file__).parent))

from cv_parser import parse_cv
from redact import redact as redact_cv
from scorer import score_candidate
from db import upsert_candidate, mark_email_sent, list_candidates, get_candidate

app = Flask(__name__, template_folder="../templates", static_folder="../static")
app.secret_key = os.environ.get("FLASK_SECRET", "kargo-dev-secret-2024")

OUTPUT_DIR = Path(os.environ.get("KARGO_OUTPUT_DIR", "/tmp/kargo_output"))
OUTPUT_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {".pdf", ".docx", ".txt"}


def _render_markdown(text: str) -> str:
    """Very small Markdown → HTML (headers, bullets, bold, code, pre)."""
    lines = text.splitlines()
    html_lines = []
    in_pre = False
    for line in lines:
        if line.startswith("```"):
            if in_pre:
                html_lines.append("</pre>")
                in_pre = False
            else:
                html_lines.append("<pre>")
                in_pre = True
            continue
        if in_pre:
            html_lines.append(line)
            continue
        if line.startswith("### "):
            html_lines.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            html_lines.append(f"<h1>{_inline(line[2:])}</h1>")
        elif line.startswith("- ") or line.startswith("* "):
            html_lines.append(f"<li>{_inline(line[2:])}</li>")
        elif line.strip() == "":
            html_lines.append("<br/>")
        else:
            html_lines.append(f"<p>{_inline(line)}</p>")
    return "\n".join(html_lines)


def _inline(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _score_and_persist(cv_path: str, role: str):
    """Parse → redact → score → write output files → persist. Returns candidate_id."""
    raw_text = parse_cv(cv_path)
    redacted, candidate_id = redact_cv(raw_text)

    result = score_candidate(redacted, role)

    # Write brief
    brief_path = OUTPUT_DIR / f"{candidate_id}_brief.md"
    rec = result.get("recommendation", "?")
    total = result.get("total_score", 0)
    dim1 = result.get("dim1_ops_exposure", {})
    dim2 = result.get("dim2_ownership", {})
    dim3 = result.get("dim3_role_fit", {})
    dim4 = result.get("dim4_communication", {})

    brief_md = (
        f"# Interview brief — {candidate_id} ({role.upper()})\n\n"
        f"Source: {cv_path}\n\n"
        f"Total score: {total}/10  ->  {rec}\n\n"
        f"## Why this ranking\n\n"
        f"- Ground-level ops exposure ({dim1.get('score',0)}/10): {dim1.get('evidence','')}\n"
        f"- Ownership under ambiguity ({dim2.get('score',0)}/10): {dim2.get('evidence','')}\n"
        f"- Role-fit ({dim3.get('score',0)}/10): {dim3.get('evidence','')}\n"
        f"- Communication ({dim4.get('score',0)}/10): {dim4.get('evidence','')}\n\n"
        f"## What to probe if this goes to interview\n\n"
        f"{result.get('interview_brief','')}\n"
    )
    brief_path.write_text(brief_md, encoding="utf-8")

    # Write email
    email_path = OUTPUT_DIR / f"{candidate_id}_email.md"
    email_path.write_text(
        f"Subject: {result.get('email_subject','')}\n\n{result.get('email_body','')}\n",
        encoding="utf-8",
    )

    upsert_candidate(candidate_id, role, cv_path, result)
    return candidate_id


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    role_filter = request.args.get("role", "").lower() or None
    candidates = list_candidates(role=role_filter)
    return render_template("dashboard.html", candidates=candidates, role_filter=role_filter)


@app.route("/score", methods=["GET", "POST"])
def score():
    if request.method == "GET":
        return render_template("score.html")

    cv_file = request.files.get("cv")
    role = request.form.get("role", "pm").lower()

    if not cv_file or not cv_file.filename:
        flash("Please select a CV file.", "error")
        return redirect(url_for("score"))

    ext = Path(cv_file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        flash(f"Unsupported file type '{ext}'. Upload a PDF, DOCX, or TXT.", "error")
        return redirect(url_for("score"))

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        cv_file.save(tmp.name)
        tmp_path = tmp.name

    try:
        candidate_id = _score_and_persist(tmp_path, role)
        flash(f"Scored {candidate_id} successfully.", "success")
        return redirect(url_for("candidate", cid=candidate_id))
    except Exception as exc:
        flash(f"Scoring failed: {exc}", "error")
        return redirect(url_for("score"))
    finally:
        os.unlink(tmp_path)


@app.route("/candidate/<cid>")
def candidate(cid: str):
    c = get_candidate(cid)
    if c is None:
        flash(f"Candidate {cid} not found.", "error")
        return redirect(url_for("dashboard"))

    brief_path = OUTPUT_DIR / f"{cid}_brief.md"
    brief_md = brief_path.read_text(encoding="utf-8") if brief_path.exists() else "_No brief file found._"
    brief_html = _render_markdown(brief_md)

    return render_template("candidate.html", c=c, brief_html=brief_html)


@app.route("/candidate/<cid>/send", methods=["POST"])
def send_email(cid: str):
    c = get_candidate(cid)
    if c is None:
        flash(f"Candidate {cid} not found.", "error")
        return redirect(url_for("dashboard"))

    if c.get("email_sent"):
        flash("Email was already sent.", "info")
        return redirect(url_for("candidate", cid=cid))

    resend_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("KARGO_FROM_EMAIL")

    if not resend_key or not from_email:
        flash("RESEND_API_KEY / KARGO_FROM_EMAIL not configured — email not sent.", "error")
        return redirect(url_for("candidate", cid=cid))

    try:
        from emailer import send_email as _send
        candidate_email = c.get("candidate_email") or ""
        _send(
            to=candidate_email,
            subject=c.get("email_subject", ""),
            body=c.get("email_body", ""),
            resend_key=resend_key,
            from_email=from_email,
        )
        mark_email_sent(cid)
        flash("Email sent successfully.", "success")
    except Exception as exc:
        flash(f"Email failed: {exc}", "error")

    return redirect(url_for("candidate", cid=cid))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print(f"\n  Kargo Hiring Agent  →  http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
