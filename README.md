# Kargo Hiring Agent

A shortlist tool for Arjun, built strictly to the case: it reads a CV, scores the
candidate against a rubric derived from Kargo's own 8 past hires (not just the
job spec), and drafts an interview brief and a candidate email (invite or
rejection). **It never sends anything on its own.** Every email waits for an
explicit, per-candidate confirmation.

Scores are persisted to **Supabase** (`candidates` table) and a local
`dashboard.csv`. CVs can be supplied from a local path or fetched directly from
a **GitHub** repository.

## Stack

| Layer | Tech |
|---|---|
| AI scoring | Gemini 2.5 Flash (`google-generativeai`) |
| Database | Supabase — project `tsgvfaiojilehdhpjrqj` |
| Email dispatch | Resend (only on explicit `send`) |
| CV sources | Local file / folder, or GitHub repo path |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
source .env            # or export each variable
```

Key variables:

| Variable | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | for real scores | AI scoring via Gemini 2.5 Flash |
| `SUPABASE_URL` | no (default set) | Supabase project URL |
| `SUPABASE_KEY` | no (default set) | Supabase publishable key |
| `RESEND_API_KEY` | for `send` only | Email dispatch |
| `KARGO_FROM_EMAIL` | for `send` only | Verified Resend sender address |
| `GITHUB_TOKEN` | for private repos | GitHub PAT for `score-from-github` |

Without `GEMINI_API_KEY`, the pipeline runs in mock mode (keyword heuristic) so
you can verify the plumbing before wiring in a real key.

## Commands

### Score one CV

```bash
python3 src/pipeline.py score --cv path/to/candidate.pdf --role pm
# or --role spm
```

Writes:
- `output/<id>_brief.md` — interview brief
- `output/<id>_email.md` — draft email (invite or rejection)
- appends to `dashboard.csv`
- upserts a row to Supabase `candidates` table

### Score a folder

```bash
python3 src/pipeline.py score-batch --dir path/to/applications/ --role pm
```

### Fetch CVs from GitHub and score them

```bash
python3 src/pipeline.py score-from-github \\
  --repo owner/repo \\
  --path applications/pm \\
  --role pm \\
  --ref main        # branch, tag, or commit (default: main)
```

Downloads all `.pdf`, `.docx`, `.txt` files under that repo path, scores each,
and writes the usual outputs. Needs `GITHUB_TOKEN` for private repos.

### List scored candidates

```bash
python3 src/pipeline.py list
python3 src/pipeline.py list --role pm
```

Prints a summary from Supabase (score, recommendation, email sent status).

### Send a drafted email

```bash
python3 src/pipeline.py send --candidate-id <id>
```

The ONLY command that calls Resend. Prompts for confirmation, sends exactly the
draft already on disk, then flips `email_sent=true` in Supabase.

## Files

| File | What it does |
|---|---|
| `src/cv_parser.py` | Reads `.docx`, `.pdf`, `.txt` into plain text |
| `src/redact.py` | Strips name, email, phone, URLs before the AI sees anything |
| `src/scorer.py` | Gemini 2.5 Flash call — returns scored JSON against the rubric |
| `src/db.py` | Supabase writes: `upsert_candidate`, `mark_email_sent`, `list_candidates` |
| `src/github_source.py` | Downloads CV files from a GitHub repo path |
| `src/emailer.py` | Transmits a pre-written draft via Resend |
| `src/pipeline.py` | CLI: `score`, `score-batch`, `score-from-github`, `send`, `list` |
| `prompts/scoring_rubric.md` | Four-dimension rubric (ops 40%, ownership 25%, role-fit 20%, comms 15%) |
| `data/job_descriptions.json` | PM and SPM job descriptions |

## Supabase schema

```sql
candidates (
  id UUID PRIMARY KEY,
  candidate_id TEXT UNIQUE,   -- e.g. "cand-8f3a"
  role TEXT,                  -- 'pm' | 'spm'
  total_score NUMERIC,
  recommendation TEXT,        -- 'interview' | 'reject'
  dim1_ops_exposure NUMERIC,
  dim2_ownership NUMERIC,
  dim3_role_fit NUMERIC,
  dim4_communication NUMERIC,
  dim1_evidence TEXT, dim2_evidence TEXT,
  dim3_evidence TEXT, dim4_evidence TEXT,
  interview_brief TEXT,
  email_subject TEXT,
  email_body TEXT,
  source_file TEXT,
  email_sent BOOLEAN DEFAULT FALSE,
  scored_at TIMESTAMPTZ DEFAULT NOW()
)
```

## What's not built (on purpose)

- No autosend — every email is drafted, never dispatched, until `send` is run by hand.
- No scoring on name, photo, college, gender, or age — `redact.py` removes these before the model sees anything.
