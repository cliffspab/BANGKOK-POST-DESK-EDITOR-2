# SIDEBAR SET — AUDIT

`110826_aud_sidebar-set`

Measured against the skill-creator criteria. Findings are ordered by
consequence, not by section.

---

## 1. PHOTO lost its measurement rules in the trim

**Functional regression, introduced today.**

PHOTO works to a DC-X character budget — "hold the DC-X budget exactly (±2
chars)", "return copy that already fits". It contains nothing about how the
counter behaves.

Grep confirms it: `paragraph break`, `setContent`, `TinyMCE` and `len()` appear
in EDIT and CHECK. They appear nowhere in PHOTO.

So PHOTO is instructed to hit a budget while blind to the three facts that
determine whether it has:

* the counter counts spaces;
* it counts a paragraph break as one char, so `\n\n` must be normalised to
  `\n` before any length check;
* the field does not refresh from a programmatic `setContent`, so a red field
  may already fit.

A caption returned as fitting will be measured against a counter behaving in a
way the skill was never told about. This was present in the longer draft and
came out when the file was cut from 157 lines to 55. The cut was right; this
went with it by accident.

**Fix:** restore the four DC-X bullets to PHOTO. Cost is roughly six lines.

---

## 2. The same mechanics are stated twice, in two different paraphrases

EDIT carries them as four bullets. CHECK carries them as prose, compressed, in
a different order, with an added inference ("a stale red field is not
overmatter").

Neither is wrong. But there is now no single authority for a mechanical fact
about the page system, and no way to detect divergence — if the counter
behaviour changes, one file gets updated and the other quietly disagrees.

This is the classic cost of the injection model: no include mechanism, so
duplication is forced. The mitigation is not to stop duplicating but to stop
duplicating *by hand*.

**Fix:** make `SIDEBAR.md` the single source and generate the four parts from
it by splitting on the page breaks. Roughly ten lines of script. Then a DC-X
correction is made once and propagates by rebuild rather than by memory.

---

## 3. Nothing has been run against real copy

There are no test cases. Not one of the four has processed a live page, a real
caption, or a filed PR document. Every judgement about them today — including
everything in this audit — is a reading of the text, not a measurement of
behaviour.

Most of what these skills produce is subjective and resists automated scoring:
headline quality, the smallest intervention, whether voice survived. Forcing
assertions onto those would measure the wrong thing.

**One thing is objectively checkable, and it is the thing most likely to
fail:** does returned copy actually sit inside the stated budget. That needs no
harness — one real overset story, one caption with a hard field cap, and a
character count taken after normalising `\n\n` to `\n`.

**Fix:** run that pair on the next shift and record the result. Two data
points beat a hundred lines of speculation.

---

## 4. Triggering optimisation does not apply here

Skill-creator's central mechanism is description tuning, because a model
normally decides for itself whether a skill is relevant. That decision does not
exist in this deployment. Invocation is explicit — `/edit`, `$pr` — so the
skill fires because it was named.

Undertriggering, the failure that description tuning exists to fix, cannot
occur. No work is warranted here.

The corollary is that the *description* field carries no load, but the
**opening line** of each part carries all of it: it is the first thing the
model reads after injection and it sets the frame. Those lines are currently
one sentence each and doing that job.

---

## 5. Rationale density

Bare imperatives — `never`, `must`, `always`, `do not` — by file:

| File  | Count |
|-------|-------|
| EDIT  | 14    |
| PR    | 4     |
| PHOTO | 1     |
| CHECK | 2     |

EDIT is the outlier. Most of its fourteen are earned — "never report an
estimated character count as verified" carries its reason in the sentence. But
several are bare: "do not truncate and do not summarise", "add no commentary
the guide does not call for".

A model given a reason generalises to the case the rule did not anticipate; a
model given a prohibition only avoids the named act. "Do not truncate" does not
prevent a model from cutting the final sentence and calling it a trim.

**Fix:** attach the reason to the three or four bare ones in EDIT. Low
priority — this is a robustness improvement, not a defect.

---

## 6. No deterministic counting anywhere

All four instruct against reporting an estimated count as verified, and none
provide a means of getting a real one. In practice that resolves to the model
estimating and declining to call it verified — which satisfies the letter and
leaves the budget unmeasured.

The obvious answer, a bundled counting script, collides with the agnostic
design: it would run in some chairs and not others.

**This is the one place where model-agnosticism has a real cost**, and it is
worth naming rather than papering over. Options, in order of preference:

1. Have the skill use a deterministic tool *where one exists*, and state
   plainly that the count is estimated where one does not. The disclosure is
   the deliverable.
2. Accept estimation everywhere and rely on the operator's final width check —
   already the stated fallback in BLUEPRINT.

Option 1 changes about two lines and makes the failure visible instead of
silent.

---

## Summary

| # | Finding | Severity | Effort |
|---|---------|----------|--------|
| 1 | PHOTO has no DC-X mechanics | High — silent mismeasurement | ~6 lines |
| 2 | Mechanics duplicated by hand | Medium — drift over time | ~10 line script |
| 3 | No live test | Medium — all claims unverified | 1 shift |
| 4 | Triggering | None — inapplicable | — |
| 5 | Bare imperatives in EDIT | Low — robustness | ~4 lines |
| 6 | No deterministic counting | Medium — invisible failure | ~2 lines |

Findings 1 and 6 are the two that can put wrong copy on a page. The rest are
maintenance.
