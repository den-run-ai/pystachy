# Model closed standard streams as None like CPython

## Problem

When descriptor 0, 1 or 2 is closed at startup, CPython makes `sys.stdin`, `sys.stdout` or `sys.stderr` `None` for the whole run. Pystachy keeps file objects, so programs diverge (documented as a deviation by #1174):

| With the stream closed | CPython | Pystachy |
|---|---|---|
| `sys.stdin.read()` | `AttributeError` | `OSError`, or reads a file that reused fd 0 |
| `print()` | prints nothing | `OSError`, or with `flush=True` writes to a file that reused fd 1 |
| `print(file=sys.stderr)` | writes to stdout | exit status 1, no message |
| `input()` read error (`0>/dev/null`) | `OSError` | `EOFError` |

## Scope

#1174 records the closed descriptors at startup and fixes `input()`'s lost-stream errors. Extend that record to the stream objects or their methods, keeping typed code's `TextIO` contract, or reject what cannot match.

## Done when

Differential cases for each row, run with `*_closed_*` names, match CPython in JIT and AOT, and the compatibility row from #1174 is removed or narrowed. Refs #1169. Prepared with Claude Code assistance.
