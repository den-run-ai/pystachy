# Contributing to Pystachy

Small fixes, tests, documentation and library ports are welcome. The same review
standards apply to everyone; prior GitHub history is not required.
Coding agents should also read [AGENTS.md](AGENTS.md) for detailed development
workflow and regression-prevention guidance.

## First contribution

1. Search [issues](https://github.com/den-run-ai/pystachy/issues) and
   [open PRs](https://github.com/den-run-ai/pystachy/pulls) for existing work. Discuss
   large features, new dependencies or architectural changes before implementing them.
2. Fork the repository and create a focused branch from current `main`. Link the
   relevant issue or describe a small reproducer; avoid unrelated cleanup.
3. Follow [source setup](docs/install.md#build-from-source) and the
   [development environment](docs/install.md#python-and-development-tools-with-uv).
   Use the Python version in [`.python-version`](.python-version) for test recordings
   and full verification. The [source map](src/README.md) explains where code lives.
4. Open a draft if work or validation is incomplete. Use the short template below.

## Issues and pull requests

Tell one story: what is difficult, what should change, and how we know it is done.
Use a specific title of **64 characters or fewer** and a complete body of **200 words
or fewer**, including code and tables (maximum 6,000 characters). Link larger repros,
logs, designs and results. Keep historical updates in comments or linked evidence.

| Submission | Three required sections |
|---|---|
| Bug, feature or gap | Problem; Scope (small repro/example and limits); Done when |
| Pull request | Problem; Change (result and limits); Validation (commands/results) |

Fill each section; no checklist or title prefix is required. Trackers link child
issues instead of repeating them. For example: `Preserve list aliases across Any`.
Include provenance/AI assistance in Change and failed, timed-out or unrun checks in
Validation. Use `Refs #N` for partial work; closing keywords are for completed scope.

The metadata workflow flags incomplete issues with `needs-description` and removes
it after correction. PRs receive a `Submission format` commit status, refreshed on
edits and pushes without rerunning compiler tests. Maintainers must require that
status in branch protection/rulesets to block merges. Issues cannot be blocked at
creation; API-created issues use the same check as the web templates. The workflow
starts after it lands on the default branch; it does not audit untouched older items.

## Repository contents

Keep research proposals, roadmaps and transient integration notes in issues or PRs;
keep raw experiments and evaluation dumps on a separate research branch. Do not
merge `research/` directories or unapplied prototype patches into `main`.
Promote useful checks into `tools/` and regression fixtures into their maintained
test locations before merging. Keep documentation focused on current tasks, APIs
and implementation contracts. Use Git history and commit-pinned PR links for
superseded designs, chronological logs and one-off audit dumps; preserve those
links wherever a current guide cites an earlier measurement. Keep reproducible
benchmark inputs and results beside their workload, and keep the current version's
release notes in `docs/releases/` for the release workflow.
`make check-repository` rejects tracked root `research` paths, even when ignored.
Tracked file and directory names must contain only ASCII letters, digits, dots,
underscores and hyphens. Tests that need spaces, brackets, Unicode or other special
characters in paths must create them in temporary directories instead of checking
them in. `make check-repository` enforces this on the Git index, including staged files.
Review the full diff for misplaced artifacts elsewhere; the path check cannot
classify a document's purpose.

## Validation

For code changes, start with a minimal regression that fails before the fix and
agrees with CPython where applicable. Record differential expectations with
`tests/record.sh` using the pinned interpreter; do not hand-edit outputs to match a bug.
See [testing](docs/testing.md) for rejection cases, ports and additional risk-specific checks.

Run from the repository root after setup; replace the example selector with affected tests:

```sh
tools/setup.sh --check
make
make test FILES="tests/programs/containers/lists.py"
make test-py FILES="tests/programs/containers/lists.py"
make lint check-recordings
```

Rebuild after compiler/runtime changes or switching branches. Behavioral changes
need complete `make verify` coverage or the corresponding CI matrix on the reviewed
revision before merge. Focused tests alone are not full verification. Documentation-only
changes need link/command review and `git diff --check`; explain that runtime tests were
not rerun. Report the tested revision, platform/toolchain, commands and results.

## Contribution rights

Submit only work you have the right to contribute under the applicable project license:
[MIT](LICENSE) for original project code; preserve third-party licenses, attribution and
[notices](THIRD_PARTY_NOTICES) for adapted material. Identify upstream sources and changes.

By submitting a pull request, you acknowledge these contribution guidelines and
confirm that you have the right to license your contribution under the project's
MIT license (or have identified and preserved licenses for included third-party
material). Contributors retain copyright; no DCO sign-off, signer registry or
contributor license agreement is required. Git history records authorship.

## AI assistance and review

AI-assisted contributions are welcome. Disclose substantial generated content
and the tools used in the PR description or a PR comment. Review and understand
the diff, verify test claims, check provenance, and be able to explain the work.
The submitting human is accountable; owner-authorized coding agents may prepare
PRs and post review comments. Private prompts and transcripts are not required.
A bot sends a one-time, non-blocking acknowledgment reminder to new PRs.

Before approving fork workflows, maintainers inspect the full diff, especially workflows,
build/test scripts, dependency changes and executable test fixtures. Run untrusted code
only in disposable isolated environments without secrets or write-capable repository credentials.
Pending workflow approval is not a test failure. Approval permits CI execution, not merge.

Merge requires maintainer review and passing applicable checks on the current revision.
For `main`, configure GitHub branch protection to require the GitHub Actions checks
`Verification` and `make lint (ruff, shellcheck, clang -Wall -Wextra)`, plus the
`Submission format` commit status. A temporary always-skipped DCO job preserves
branch-protection compatibility until its required status is removed.
Apply the rule to administrators and other
credentials with bypass access. Documentation-only changes still receive `Verification`.

New changes need renewed review and validation. Passing CI does not resolve open design
or security concerns. Accepted contributions do not grant write or release access.
