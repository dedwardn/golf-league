---
name: audit
description: Independent read-only review of the uncommitted changes against the architecture and spec.
disable-model-invocation: true
context: fork
agent: reviewer
background: false
---

Review the uncommitted changes in this repository.

Changed and new files:

!`git status --short || true`

Diff of tracked files:

!`git diff HEAD || true`

Read every new (untracked) file listed above in full, since it is not in the diff. Then review as your instructions describe and report.
