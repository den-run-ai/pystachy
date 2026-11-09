# Cut the program-cache hit's fixed 36 ms launch cost

## Problem

On main `ce8c887`, a `pystachy run` program-cache hit takes about 37 ms even for hello-world, while the cached executable alone runs in 1.5 ms. CPython starts and runs the JSON-repair port in 33 ms, so cached runs gain nothing at launch.

| `bench/json_repair/bench.py 0`, one pinned CPU, 40 runs | Time |
|---|---:|
| `pystachy run`, cache hit | 37.8 ms |
| Cached executable, run directly | 1.46 ms |
| AOT executable | 1.41 ms |
| CPython 3.13, port / upstream | 32.8 / 38.8 ms |

## Scope

`PYSTACHY_TIMING` puts 33.2 ms in cache lookup. An strace timeline attributes it to:

- re-statting about 6,800 toolchain search paths (33,793 `newfstatat` calls, 15.5 ms);
- eight helper processes (`sh`, `stat`, `touch`; 6.6 ms);
- reading and hashing a 717 KB manifest (5.5 ms).

Keep every invalidation rule in docs/program-cache.md.

## Done when

A hello-world hit adds at most 5 ms over running its executable directly, measured as above, and `make test-program-cache` and its probe still pass. Refs #1103. Prepared with Claude Code assistance.
