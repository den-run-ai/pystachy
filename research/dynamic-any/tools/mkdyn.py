"""Copy modules or packages into DST with '# pystachy: dynamic-any' as each .py file's first line.

usage: python3.13 -I mkdyn.py DST SRC...   (SRC: a .py file or a package directory)
"""
import os
import shutil
import sys

PRAGMA = "# pystachy: dynamic-any\n"


def inject(src: str, dst: str) -> None:
    with open(src, encoding="utf-8") as f:
        text = f.read()
    with open(dst, "w", encoding="utf-8") as f:
        f.write(PRAGMA + text)


def main() -> None:
    dst = sys.argv[1]
    os.makedirs(dst, exist_ok=True)
    for src in sys.argv[2:]:
        src = os.path.realpath(src)
        name = os.path.basename(src)
        if os.path.isdir(src):
            for root, dirs, files in os.walk(src):
                dirs[:] = [d for d in dirs if d != "__pycache__"]
                rel = os.path.relpath(root, src)
                out = os.path.join(dst, name, rel)
                os.makedirs(out, exist_ok=True)
                for fn in files:
                    if fn.endswith(".py"):
                        inject(os.path.join(root, fn), os.path.join(out, fn))
                    elif not fn.endswith(".pyc"):
                        shutil.copyfile(os.path.join(root, fn), os.path.join(out, fn))
        else:
            inject(src, os.path.join(dst, name))


main()
