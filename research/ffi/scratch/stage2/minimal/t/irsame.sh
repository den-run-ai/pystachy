#!/bin/sh
# $1 = program; compares IR + messages + status of the original and patched compilers
f="$1"
a=$(PYSTACHY_HOME=$PWD build/orig1 ir "$f" 2>&1; echo "rc=$?")
b=$(PYSTACHY_HOME=$PWD ./pystachy ir "$f" 2>&1; echo "rc=$?")
if [ "$a" = "$b" ]; then echo same; else echo "DIFF $f"; fi
