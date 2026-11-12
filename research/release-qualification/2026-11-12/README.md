# Pystachy v0.4.0 qualification evidence

This branch retains release and candidate qualification evidence. It is not a source integration branch and must not be merged into main.

Alpha.6 was published from `0b13a2121014d8256954c6af50339ff0de8dac62`. See `alpha6/release-gates.json` for exact-main qualification and source-delta records, and `alpha6/audit.md` / `alpha6/audit.json` for tested-versus-public artifact verification.

RC.1 was published and publicly verified from `30822255ee7ee704e0e780e01cd8c23357ba13ab`, merged through PR #1389. See [the qualification and publication report](rc1/audit.md) and its compact public-artifact evidence bundle.

RC.2 is separately qualified in draft PR #1403 at `1a53d86c5fb81514d8cd9bd3f2e264f51849fdcb`. [Its report](rc2/audit.md) records the retained compiler comparison, independent reviews, initial Lint correction and fresh final-source qualification. Full candidate GC/platform CI remains pending at this checkpoint.

Candidate checks and exact merged-main release qualification remain distinct. CI headroom and GC scaling requirements stay open under #1178, #1179 and #1181 until their own acceptance criteria are met. Alpha.6's milestone is closed; the broader v0.4.0 milestone remains open.
