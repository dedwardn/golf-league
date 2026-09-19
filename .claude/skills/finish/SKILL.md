---
name: finish
description: Close the current build step. Runs the quality gate, writes the step report and proposes the commit.
disable-model-invocation: true
argument-hint: "[step id, for example S3]"
---

Close build step $ARGUMENTS.

1. Run `./scripts/check.sh`. If it fails, fix the cause and rerun. Never weaken a check, skip a test, add an ignore comment or change `pyproject.toml` to get to green. If you cannot get to green honestly, stop and explain.
2. Compare the diff with the approved plan. List every difference.
3. Write `docs/steps/$ARGUMENTS.md` with these headings and nothing else:
   - **Implemented**: what now exists, in plain language, five lines at most.
   - **Where**: each file touched and what it holds.
   - **Public API**: every public function or class added or changed, with signature.
   - **Deviations from plan**: each one with its reason, or "none".
   - **Deliberately not done**: what was left out and which step owns it.
   - **Open questions**: for the owner.
4. Update the module map in `docs/ARCHITECTURE.md` if the public API changed, and set the step's status to `done` in `docs/BUILD_PLAN.md`.
5. Show `git status --short` and propose one commit message of the form `$ARGUMENTS: <what was added>`. Do not commit until the owner says so.
