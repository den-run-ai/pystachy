"""Corpus and compiler-size metrics at commits.

usage: python3 -I corpus_at.py REPO SHA...
Prints: sha date programs deviations errors total compiler_py_lines runtime_lines lib_py_files
Corpus layout: tests/programs/*/*.py, tests/deviations/*.py, tests/errors/*/*.py (since 2026-10-20),
before that tests/*.py, tests/deviations/*.py, tests/errors/*.py.
"""
import re
import subprocess
import sys

repo = sys.argv[1]


def git(*a):
    return subprocess.run(['git', '-C', repo, *a], check=True, capture_output=True, text=True).stdout


for sha in sys.argv[2:]:
    names = git('ls-tree', '-r', '--name-only', sha).splitlines()
    new = 'tests/corpus.sh' in names
    if new:
        prog = [n for n in names if re.fullmatch(r'tests/programs/[^/]+/[^/]+\.py', n)]
        err = [n for n in names if re.fullmatch(r'tests/errors/[^/]+/[^/]+\.py', n)]
    else:
        prog = [n for n in names if re.fullmatch(r'tests/[^/]+\.py', n)]
        err = [n for n in names if re.fullmatch(r'tests/errors/[^/]+\.py', n)]
    dev = [n for n in names if re.fullmatch(r'tests/deviations/[^/]+\.py', n)]
    comp = [n for n in names if re.fullmatch(r'(src/pystachy_compiler/[^/]+\.py|pystachy\.py|compiler/[^/]+\.py)', n)]
    rt = [n for n in names if re.fullmatch(r'(runtime/runtime\.py|runtime\.py|runtime/[^/]+\.(c|h|py)|runtime\.c)', n)]
    def lines(paths):
        if not paths:
            return 0
        out = git('cat-file', '--batch', input=None) if False else None
        total = 0
        p = subprocess.run(['git', '-C', repo, 'cat-file', '--batch'], input=''.join(f'{sha}:{x}\n' for x in paths),
                           capture_output=True, text=True, check=True).stdout
        # Each object: header line then content; count newlines in contents.
        i = 0
        while i < len(p):
            nl = p.index('\n', i)
            hdr = p[i:nl].split()
            size = int(hdr[2])
            content = p[nl + 1: nl + 1 + size]
            total += content.count('\n')
            i = nl + 1 + size + 1
        return total
    date = git('show', '-s', '--format=%cI', sha).strip()
    print(sha[:8], date[:16], len(prog), len(dev), len(err), len(prog) + len(dev) + len(err),
          lines(comp), lines(rt), sep='\t')
