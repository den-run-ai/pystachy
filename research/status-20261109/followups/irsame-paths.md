# Normalize library paths in irsame's IR comparison

## Problem

`make irsame REF=ce8c887` reports about 264 of 4,345 corpus programs as different when nothing changed. Each compiler embeds its own library path in IR string constants, such as CPython's `cannot import name 'abc' from 'collections' (.../lib/collections/__init__.py)` message: the reference compiler writes `build/ref/lib/...`, the candidate `lib/...`. On 40 `tests/programs/imports` cases, 7 differ only this way. `tools/irsame.sh` normalizes library prefixes in diagnostics only, so every real difference hides among these.

## Scope

Four agents hit this on 9 November while validating #1171–#1176 and fell back to one shared home with byte-identical `lib/` and runtime, which AGENTS.md allows only with identical inputs. Normalize each compiler's own library prefix in IR string constants as for diagnostics, or stop embedding absolute library paths where CPython's message permits.

## Done when

`make irsame REF=<head>` against an unchanged tree reports no differences, a seeded IR change is still reported, and docs/testing.md describes the normalization. Prepared with Claude Code assistance.
