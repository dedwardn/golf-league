---
name: step
description: Plan one build step from docs/BUILD_PLAN.md. Produces a plan only and never writes code.
disable-model-invocation: true
argument-hint: "[step id, for example S3]"
---

Plan build step $ARGUMENTS. Do not write or edit any file in this turn.

## Current state

Uncommitted changes (must be empty before a new step starts):

!`git status --short || true`

Every public function and class that already exists:

!`grep -rnE "^(def|class|async def) [a-zA-Z]" src/league || true`

## What to do

1. Read, in this order: `docs/BUILD_PLAN.md` (only the section for $ARGUMENTS), `docs/ARCHITECTURE.md`, and the rules in `docs/SPEC.md` that the step names. Read the source modules the step touches. Read nothing else.
2. If the working tree is not clean, or an earlier step is not marked done, stop and say so.
3. Reply with a plan in exactly this shape:

**Step**: id and title.
**Understanding**: two or three sentences, in your own words, of what this step adds.
**Files**: every file you will create or change, with one line on why that file is the right home. A new file needs a reason why no existing file fits.
**Public API**: each new or changed public function or class with its full signature and a one-line contract.
**Reuse**: which existing functions from the list above you will call, and which ones you considered and rejected, with the reason.
**Tests**: the test cases you will write, named after the worked examples in the spec.
**Not doing**: what is near this step but out of scope.
**Questions**: anything in the spec that is ambiguous or seems wrong. Ask, do not guess.

4. Wait for approval. If the step cannot be done in one reviewable change (about 300 changed lines including tests), propose a split.
