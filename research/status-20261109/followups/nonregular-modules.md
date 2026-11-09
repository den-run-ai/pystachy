# Ignore non-regular NAME.py files when resolving imports

## Problem

A directory named `NAME.py` or `NAME/__init__.py` beside a program makes `import NAME` crash the compiler with `IsADirectoryError`, and a FIFO with either name makes it hang. CPython's path finder accepts only regular files there and moves on. The driver's `ffi.py` probes test existence the same way.

## Scope

Found while fixing #1166 (PR #1173) on main `ce8c887`. `Loader.filepath` checks the `.py` and `__init__.py` candidates with `tracked_exists`. After #1173, program-cache probes record each candidate's kind (directory, regular file, other, missing), so requiring a regular file is cache-safe.

## Done when

`import NAME` ignores a non-regular `NAME.py` or `NAME/__init__.py` as CPython does, the driver's `ffi.py` probes do the same, and differential and program-cache cases cover a directory, a FIFO and a symlink to a file. Refs #1166. Prepared with Claude Code assistance.
