# Working with Claude Code on this repo

For the owner. The agent's rules are in CLAUDE.md. This page is how you drive.

## The loop, one step per session

1. **Freeze the step.** Read the step in BUILD_PLAN.md and the rules it names in SPEC.md. If a rule lacks a worked example for a case you care about, add it now. Examples are the contract: they become the tests.
2. **Start clean.** `git status` is empty. Open `claude` in the repo. Sessions start in plan mode by setting.
3. **`/step S3`.** The skill injects the list of every existing public function, so the agent sees what it can reuse before it plans. Read the plan. Check three things: the files are the ones ARCHITECTURE.md assigns, the public API is as small as the step needs, and the "Reuse" and "Questions" parts are real. Answer the questions. Edit the plan until you would be happy to read that diff.
4. **Approve.** The agent leaves plan mode, writes tests from the examples, then code. Watch the first file. If it drifts, press Esc and correct at once. After two failed corrections, `/rewind` or `/clear` and restate the step with what you learned. Do not argue a session back on track.
5. **`/finish S3`.** Gate, step report, module map, proposed commit. Read `docs/steps/S3.md`. It should match what you saw.
6. **`/audit`.** A reviewer with no memory of the session and no write access reads the change against the architecture. Treat findings as input, not orders. Fix in the same session only what belongs to this step.
7. **Commit yourself**, then `/clear` or close. Never start the next step in a used session.

## Habits that keep it tight

- One thing per session. A second request in the same session is how structure erodes.
- Small steps. If a plan lists more than about five files or 300 changed lines, split the step before coding.
- You own the docs. The agent may propose edits to SPEC, ARCHITECTURE and DECISIONS, and the permission prompt shows you each one.
- Promote prose to checks. When the agent breaks a rule twice, do not add a sentence to CLAUDE.md. Add a lint rule, a test or a line in `check_structure.py`. Keep CLAUDE.md under about 120 lines.
- New dependency means a decision. `uv add` prompts you. Ask what it replaces and whether twenty lines of code would do.
- Read diffs, not summaries. `git diff` before every commit.
- When you change your mind about a rule, change SPEC.md first, in its own commit, then run a step that implements the change.

## Where to think and where to build

Use the claude.ai project (this research thread) to decide what the league should do: formats, season design, rule wording, worked examples. Use Claude Code only to implement a frozen step. Mixing the two in one session is the main source of bloat.

## Optional later

- A GitHub Action that runs `scripts/check.sh` on every push.
- Headless review in CI: `claude -p "/audit"` on pull requests.
- A nested `CLAUDE.md` in `src/league/web/` once templates exist, with the few template conventions. Nested files load only when the agent works in that folder.
