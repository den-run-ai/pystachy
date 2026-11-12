import argparse
import json
import re
import textwrap
import fnmatch


def main() -> None:
    p = argparse.ArgumentParser(prog="demo")
    p.add_argument("--n", type=int, default=3)
    a = p.parse_args([])
    data = json.loads('{"a": [1, 2, 3], "b": "text"}')
    print(json.dumps(data))
    print(re.sub(r"[aeiou]", "_", "an import-heavy program"))
    print(textwrap.fill("the quick brown fox jumps over the lazy dog " * 3, width=30))
    print(fnmatch.fnmatch("file.py", "*.py"), a.n)


main()
