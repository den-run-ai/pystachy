# Contributing to Pystachy

Small fixes, tests, documentation and library ports are welcome. The same review
standards apply to everyone; prior GitHub history is not required.

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
4. Open a draft if work or validation is incomplete. Fill in the PR template with
   actual evidence, including failures, timeouts and checks you could not run.

## Validation

For code changes, start with a minimal regression that fails before the fix and
agrees with CPython where applicable. Record differential expectations with
`tests/record.sh` using the pinned interpreter; do not hand-edit outputs to match a bug.
See [testing](docs/testing.md) for rejection cases, ports and additional risk-specific checks.

Run from the repository root after setup; replace the example selector with affected tests:

```sh
tools/setup.sh --check
make
make test FILES="tests/lists.py"
make test-py FILES="tests/lists.py"
make lint check-recordings
```

Rebuild after compiler/runtime changes or switching branches. Behavioral changes
need complete `make verify` coverage or the corresponding CI matrix on the reviewed
revision before merge. Focused tests alone are not full verification. Documentation-only
changes need link/command review and `git diff --check`; explain that runtime tests were
not rerun. Report the tested revision, platform/toolchain, commands and results.

## Rights and sign-off

Submit only work you have the right to contribute under the applicable project license:
[MIT](LICENSE) for original project code; preserve third-party licenses, attribution and
[notices](THIRD_PARTY_NOTICES) for adapted material. Identify upstream sources and changes.

New PRs opened after this guide is merged require each contributor's own
[Developer Certificate of Origin 1.1](https://developercertificate.org/) sign-off on
each new non-merge commit they author in the PR. After reading the DCO, use `git commit -s` to add
`Signed-off-by: Your Name <your-email>` with your own identity. Never add someone else's
sign-off on their behalf. Sign-offs remain in public history; they are provenance
attestations, not cryptographic signatures or security verification.

Maintainers check sign-offs manually until automated enforcement is configured.
Already-open PRs follow the existing process; do not rewrite merged history to add
sign-offs. No separate CLA is required.

## AI assistance and review

AI-assisted contributions are welcome. Disclose substantive generated code or text
and the tools used in the PR. Review and understand the whole diff, verify test claims,
check provenance, and be able to explain or revise the work. The submitter remains
responsible for it; private prompts and conversation transcripts are not required.

Before approving fork workflows, maintainers inspect the full diff, especially workflows,
build/test scripts, dependency changes and executable test fixtures. Run untrusted code
only in disposable isolated environments without secrets or write-capable repository credentials.
Pending workflow approval is not a test failure. Approval permits CI execution, not merge.

Merge requires maintainer review and passing applicable checks on the current revision;
new changes need renewed review and validation. Passing CI does not resolve open design
or security concerns. Accepted contributions do not grant write or release access.
