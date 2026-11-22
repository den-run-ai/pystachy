#!/bin/sh
# pre-commit runs this script from the consumer's checkout and can pass several paths.
compiler=$(dirname "$0")/../pystachy.py
status=0
for file do
    case "$file" in -*) file=./$file ;; esac
    python3 -E "$compiler" check "$file" || status=1
done
exit "$status"
