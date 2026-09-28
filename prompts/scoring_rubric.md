# Kargo Candidate-Scoring Rubric

This is the rubric derived from Kargo's 8 past hires (see `hires/`), not the job
spec alone. Every past hire rated "Exceeds Expectations" has direct, ground-level
logistics or freight-operations exposure before joining Kargo, regardless of the
function they were hired into (engineering, ops, sales, customer success, or
product). Every hire without that exposure capped out at "Meets Expectations" or
fell to "Below Expectations." That split held for all 8 hires. This is the
signal the job description only hints at ("familiarity ... is a genuine
advantage, not a nice-to-have") and that eleven weeks of evaluating against the
spec alone has missed.

Score every candidate on these four dimensions, for the specific role (PM or
SPM) they applied to. Weights sum to 100.

## 1. Ground-level operations/logistics exposure — 40%

Look for hands-on TIME INSIDE a freight, shipping, customs, port, 3PL, or
comparably ops-heavy operation — not adjacent SaaS built for such industries,
working inside the operation itself. Evidence: job titles at freight
forwarders, CHAs, ports, carriers, 3PLs; day-to-day handling of shipments,
documentation, customs, or carrier coordination; direct language about how the
operation actually runs.

- 9-10: multiple years working inside such an operation directly
- 5-8: some direct exposure, or close and sustained work with such operators
- 1-4: exposure only through customer-facing SaaS work for such customers, no
  hands-on operational role
- 0: no evidence of exposure in either form

## 2. Ownership under ambiguity — 25%

Look for self-initiated fixes, features shipped AND killed with a stated
reason, decisions made and documented without a senior layer signing off,
visible post-mortems or retros, "built X after noticing Y, adopted within Z."

- 9-10: multiple concrete instances of independent, consequential decisions,
  with follow-through and a documented outcome
- 5-8: some independent ownership, but within a structure with more oversight
- 1-4: mostly executes what others decided
- 0: no evidence either way

## 3. Role-fit against the named JD — 20%

Use `data/job_descriptions.json` for the role applied to. PM: 2-4 years,
first-time-building environments. SPM: 5-8 years, owning a product area
without a senior-PM layer above them, platform/integration experience.

- 9-10: experience band matches and the evidence backs up the JD's specific
  asks (shipped+killed for PM; owns an integration/architecture area for SPM)
- 5-8: adjacent but not exact fit (right years, different kind of ownership,
  or vice versa)
- 1-4: significant mismatch in years or type of ownership
- 0: no PM/SPM experience at all

## 4. Communication of reasoning — 15%

A proxy for the rationale Arjun currently has no record of. Reward specific,
quantified claims (numbers, timeframes, named outcomes) over generic
responsibility statements.

- 9-10: consistently specific and quantified throughout
- 5-8: some specifics, some generic filler
- 1-4: mostly generic responsibility statements
- 0: no substantive claims to assess

## Combining scores

`total = 0.40*dim1 + 0.25*dim2 + 0.20*dim3 + 0.15*dim4`, each dim scored 0-10,
giving a total out of 10.

A candidate who scores high on role-fit (dim 3) but 0-1 on ground-level
exposure (dim 1) should rank BELOW a candidate with a slightly thinner years
count who clears both dim 1 and dim 2 — this is the explicit correction to
eleven weeks of evaluating against the spec alone. Do not let dim 3 alone
carry a candidate to the top of the list.

## What NOT to score on

Name, gender, age, photo, college pedigree/brand, or anything not tied to one
of the four dimensions above. Do not infer these even if a redaction was
imperfect — score only the work history and its evidence.

## Output format

Return strict JSON:

```json
{
  "dim1_ops_exposure": {"score": 0-10, "evidence": "1-2 sentences, specific"},
  "dim2_ownership": {"score": 0-10, "evidence": "..."},
  "dim3_role_fit": {"score": 0-10, "evidence": "..."},
  "dim4_communication": {"score": 0-10, "evidence": "..."},
  "total_score": 0-10,
  "recommendation": "interview" | "reject",
  "interview_brief": "who they are, why they ranked here, what to probe if Arjun moves forward - 3-5 sentences",
  "email_subject": "...",
  "email_body": "the full draft email - interview invite or a respectful, specific rejection - in Arjun's voice, first person"
}
```

`recommendation` is "interview" only when `total_score >= 6.0`. This threshold
is a starting point, not a fixed law — it exists so every candidate, including
the ones who don't clear it, gets a drafted response instead of silence.
