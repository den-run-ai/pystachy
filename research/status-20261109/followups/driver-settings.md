# Clean up after rejected settings and stray PYSTACHY_ARGV0

## Problem

Two driver defects found while fixing #1168 (PR #1171) on main `ce8c887`:

- A launch rejected for an invalid setting, such as `PYSTACHY_JIT_INLINE=`, exits 1 but leaves the driver's temporary directory behind, cached or not.
- `PYSTACHY_ARGV0` is the JIT runtime's private handoff for `sys.argv[0]`. When a caller's environment already contains it, it replaces the compiler's own `argv[0]` and breaks the compiler, on cached and uncached paths.

## Scope

Remove the temporary directory on every rejection path. Ignore or clear an inherited `PYSTACHY_ARGV0` before the compiler uses it, keeping the program's handoff intact.

## Done when

Repeated rejected launches leave no temporary directories, a compiler started with `PYSTACHY_ARGV0` set behaves as without it, and tests cover both on the cached and uncached paths. Refs #1168. Prepared with Claude Code assistance.
