# Kargo Hiring Agent

A shortlist tool for Arjun, built strictly to the case: it reads a CV, scores the
candidate against a rubric derived from Kargo's own 8 past hires (not just the
job spec), and drafts an interview brief and a candidate email (invite or
rejection). **It never sends anything on its own.** Every email waits for an
explicit, per-candidate confirmation — see `docs: the Cut` in the Automation
Brief doc for why.

## What this is (and isn't)

This is the pipeline behind the "Hiring dashboard" in the Components Map:
Trigger → Input → Context → Processing → AI → Output, as one command-line
run per CV, writing its results into a shared `dashboard.csv` and a set of
per-candidate draft files. It is not a hosted web app with logins — the case
is one founder, one screen, and this is sized to that.

## Setup

```bash
pip install -r requirements.txt
export GEMINI_API_KEY=AQ....             # your own key — used to score & draft
export RESEND_API_KEY=re_...             # your own key — used only to send, only on --send
export KARGO_FROM_EMAIL="Arjun Mehta <arjun@kargo.example>"   # must be a Resend-verified sender
```

Without `GEMINI_API_KEY` set, the pipeline runs in `--mock` mode: it uses a
transparent rule-based stand-in for the LLM call (see `src/scorer.py:mock_score`)
so you can see the mechanics end to end before wiring in a real key. Mock scores
are NOT a substitute for the real rubric — they exist only to prove the pipeline
runs.

## Run it

Score one CV against a role:

```bash
python3 src/pipeline.py score --cv path/to/candidate.docx --role pm
# or --role spm
```

This appends a row to `dashboard.csv` (rank, score, rationale, redacted
candidate id) and writes `output/<candidate_id>_brief.md` (interview brief) and
`output/<candidate_id>_email.md` (draft email — invite or rejection, decided by
whether the score clears the bar for that role).

Score everything in a folder at once:

```bash
python3 src/pipeline.py score-batch --dir path/to/applications --role pm
```

Review `dashboard.csv` and the drafts. When Arjun has decided:

```bash
python3 src/pipeline.py send --candidate-id <id>
```

This is the ONLY command that calls Resend, and it sends exactly the draft
already sitting in `output/<id>_email.md` — nothing is regenerated or
reworded at send time, so what Arjun reviewed is what goes out.

## Files

- `src/redact.py` — strips name, email, phone, and photo references from the
  extracted CV text before it is sent to the AI. The AI scores the work
  history, not the person.
- `src/cv_parser.py` — reads `.docx`, `.pdf`, and `.txt` CVs into plain text.
- `src/scorer.py` — the AI call (Gemini 2.0 Flash): scores a redacted CV
  against `prompts/scoring_rubric.md` for the named role, returns score +
  rationale + interview-brief + draft email as structured JSON.
- `src/emailer.py` — sends a pre-written draft via Resend. Takes no free-form
  text generation; it only transmits what's already on disk.
- `src/pipeline.py` — the CLI: `score`, `score-batch`, `send`.
- `prompts/scoring_rubric.md` — the actual rubric (weights + evidence) as given
  to the model, word for word from the Automation Brief doc.
- `data/job_descriptions.json` — the two JDs from `jds/`, used as the role-fit
  reference inside the rubric.

## What's not built here (on purpose)

- No autosend. Every email is drafted, never dispatched, until `send` is run
  by hand for that one candidate.
- No scoring on name, photo, college pedigree, gender, or age — `redact.py`
  removes these before the CV reaches the model.
- No auto-reply to the two candidates Arjun already told "let's chat" —
  that's a real conversation he owes them, not a template.
