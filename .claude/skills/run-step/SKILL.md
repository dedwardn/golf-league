---
name: run-step
description: Carry one build step from plan to a proposed commit, with the architect agent reviewing the plan and the audit findings, stopping wherever the owner is needed.
disable-model-invocation: true
argument-hint: "[step id, for example S9a]"
---

Carry build step $ARGUMENTS through plan, build, finish and audit in this session. You are the builder. The `architect` agent reviews in the owner's place, except where it sends a question to the owner.

## Current state

Uncommitted changes (must be empty before a new step starts):

!`git status --short || true`

Every public function and class that already exists:

!`grep -rnE "^(def|class|async def) [a-zA-Z]" src/league || true`

## Phases

1. **Plan.** Do steps 1 and 2 under "What to do" in `.claude/skills/step/SKILL.md`, using the state above, and write the plan in the shape its step 3 gives, including a split if its step 4 calls for one. Do not present it yet.
2. **Architect.** Send the `architect` agent the step id, "plan review" and the full plan. Revise the plan to follow its rulings, and send it back once more if the revision changed the plan's shape. If the verdict is "stop for the owner", or the plan and the architect still disagree after the second round, present both and stop.
3. **Owner approval.** Present the final plan, the architect's rulings, its doc edits and any owner questions. Say that approval also covers committing the doc edits on their own. Wait for approval.
4. **Build.** Apply the doc edits and commit them on their own with a message of the form `Docs: <what changed>`. Then write the tests, then the code, touching only the files in the approved plan. If you need another file, stop and say so.
5. **Finish.** Do steps 1 to 4 of `.claude/skills/finish/SKILL.md`.
6. **Audit.** Send the `reviewer` agent "Review the uncommitted changes in this repository", the output of `git status --short`, the output of `git diff HEAD`, and the paths of the untracked files, which it reads in full.
7. **Architect on findings.** Send the `architect` agent the step id, "findings review", the findings verbatim and the step report's path. Apply what it accepts and its doc edits, rerun `./scripts/check.sh`, and record every finding's outcome in the step report: applied, declined with the reason, or sent to the owner.
8. **Stop for the owner.** Present the gate result, the audit outcome, the owner questions, `git status --short` and the commit you propose, `$ARGUMENTS: <what was added>`. Commit only when the owner says so. Never push.
9. **Hand over.** After the commit, end with three lines and nothing else: what is committed, with hashes; whether the tree is clean and what is left to push, which the owner does, since this session cannot push; and the next step, the first one marked todo in `docs/BUILD_PLAN.md`, with the exact command to start it in a cleared session, for example `/run-step S9b`.

## Stop early

Stop and present what you have when the gate cannot be made green honestly, when you need a file outside the plan, or before anything that touches `pyproject.toml`, `scripts/`, `.claude/` or `CLAUDE.md`. An owner question that does not block the step waits for phase 8.
