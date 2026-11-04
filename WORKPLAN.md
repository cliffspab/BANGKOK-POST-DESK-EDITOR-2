# BKP Desk shared workplan

This is the supervisor-and-custodian working record for planned changes to the
Blueprint beta and its delivery machinery. It is not editorial authority.
`Blueprint/BLUEPRINT.md` remains the beta source; published editorial work is
governed by the applicable Blueprint delivery.

## Current position

- Published beta commit: `bfb83cc` (`301026_gpt_bkp3-1`).
- Live native-document edition: `301026_gpt_bkp3-1`.
- Delivery direction: installed skills are replacing Shift as the active
  handover route.
- `Shift/` is deprecated and retained empty as a reusable stable named space.
  It is not to be refreshed or mirrored.

## Change set in preparation

Edition: `301026_gpt_bkp3-1`

Status: published and synchronized. The source, five skill archives and all
seven permanent Google Docs passed readback; content was updated before Boot.
Word/PDF are deliberately out of scope. Permanent document IDs and their unique
`*_bkp3-0` titles remain unchanged.

### Copy-bearing returns

Every assistant turn that returns copy to chat must put that copy in a fenced
copy box. A `HOLD:` or `Query:` notice is one line immediately above the box.
No copy is returned unboxed, including held copy and replacement copy in a
follow-up.

### Domestic filing record

For domestic news-desk copy only, append the exact original filing as received,
unmarked, after the Style Log. The candidate labels it `ORIGINAL FILING`, leaves
it unfenced as the sole archival exception to the copy-box rule and places it
before `OUTSTANDING`.

### Check/QC

Add a QC use to Check:

> QC: Review another operator's Job Report. Ensure the facts are correct and
> Bangkok Post style is applied. List changes required and await guidance.

The candidate treats `QC` as an explicit Check command, lists required changes
without rewriting and returns `Clear to initial.` when no change is required.

### Mode duration

A mode lasts one turn. It does not carry into the next assistant turn unless
the supervisor invokes it again.

### Cabinet reference

The current Thai Cabinet is a standing, dated section in the Desk
Addendum rather than restoring volatile people records to the Directory. The
section is sourced to the Royal Thai Government, states when it was checked
and remains subject to the Addendum's existing `[P2]` and supersession rules.

It is discoverable from the package entry: Boot points directly to the Desk
Addendum, and Edit tells the model to consult its Cabinet section when a Thai
minister or portfolio is material. The Addendum remains the single published
copy; do not duplicate the roster inside `DEPLOY` or the skill archives.

The first roster was extracted programmatically from all seven pages of the
official current-Cabinet register and checked against the Royal Command. Its
refresh is explicit rather than scheduled in this payload; an unattended
refresh mechanism remains future work and must never replace a valid roster
with an empty or partial fetch.

## Decisions resolved

- `ORIGINAL FILING` is the label for the unfenced archival copy.
- It sits before `OUTSTANDING`, preserving `CLEARED:` as the final line.
- `QC` is a distinct command rather than an automatic part of every Check.

## Publication discipline

- Work first in an isolated candidate.
- Add every new addition or material change to the user-facing `CHANGELOG.md`;
  name affected deliveries and the user's update action, keep unpushed work
  under **Unreleased**, and give every published version its own entry.
- Rebuild all generated deployments and upload archives.
- Record the exact approved payload in `COMMITS-PENDING.md`.
- The supervisor reviews the guarded preflight and performs the push.
- During the beta, GitHub validation runs; edition sealing, Shift refresh and
  pCloud sync remain paused.
