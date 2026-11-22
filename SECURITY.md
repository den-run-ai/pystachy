# Security policy

## Report a vulnerability

Report suspected vulnerabilities privately with GitHub's
[private vulnerability reporting](https://github.com/den-run-ai/pystachy/security/advisories/new),
not in a public issue, pull request or discussion. Include:

- the output of `pystachy --version` and `pystachy doctor`, and your platform;
- a minimal program or the steps that reproduce the problem;
- what you observed and what an attacker could achieve.

Report against the latest release or current `main`. Fixes ship in a new
release ([releasing](docs/releasing.md)).

## Scope

In scope:

- memory-safety faults, crashes and silent wrong results in executables, extension
  modules and JIT runs of programs that Pystachy accepts;
- the runtime (`runtime.c`, `runtime.py`, `lib/`) and the FFI boundary;
- the pip and uv launcher's LLVM download and its checksum verification
  (`pystachy_toolchain.py`);
- release archives, Docker images and the workflows that publish them.

Compiling a program runs code you supply, as running it under CPython does:
compile only source you trust. A program that Pystachy rejects is not a
vulnerability; report it as an ordinary issue.
