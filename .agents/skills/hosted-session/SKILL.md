---
name: hosted-session
description: Work in a hosted or cloud agent session on Pystachy (Codex cloud, Claude Code on the web, other containers with tool timeouts). Use at the start of such a session, before long builds, verification or benchmarks, and when a container restarts or an operation is denied.
---

# Hosted agent sessions

These rules extend [AGENTS.md](../../../AGENTS.md) for sessions that run in a container or
behind a tool timeout.

- Check for a shallow clone (`git rev-parse --is-shallow-repository`); deepen before
  `make irsame`, merge-base checks or history searches (`git fetch --deepen=200 origin main`).
- Use pinned development tools, not whatever the container preinstalls. Package smoke
  needs `tools/requirements-packaging.txt`. If `/usr/bin/time` or `perf` is absent,
  use `/proc/PID/status`'s `VmHWM` for peak memory and callgrind for profiling.
- Builds can exceed a shell tool's default timeout (Claude Code commonly defaults to
  two minutes). Use the harness's background mode with logs and completion notices.
- Containers/worktrees can vanish or restart on OOM. Run one heavy build, valgrind or
  timing job at a time; push validated work and preserve cited commands/results in its
  PR. Keep scratch files outside the repo; stop hooks may require a clean checkout.
- Confirm tools and permissions in this session; AGENTS.md covers denied operations.
  Prefer plain pushes and merges. Re-read live PR state and the current branch after
  delayed events or worktree conflicts. Connector writes can alter spacing and JSON
  decodes Unicode escapes: verify published content.
- Long GitHub listings (workflow jobs, artifacts) can exceed a tool's output limit; save
  them to files and parse them there. Artifact downloads return short-lived signed URLs:
  fetch each one right after requesting it.
