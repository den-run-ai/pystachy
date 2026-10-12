"""Sort the "Pystachy port:" markers of ports by cause, with keyword rules (#171, section 2).

python3 research/ports/port_markers.py [DIR | REF ...]
A DIR is a port's directory (default: each directory under ports/); a REF is a branch whose
ports/ files differ from origin/main, such as origin/claude/port-sgp4. The rules are heuristic;
tools/port_edits.py (#182) is this classifier as a tool, with the census check of a port added.
"""
import collections
import os
import re
import subprocess
import sys

def git(*a):
    return subprocess.run(("git",) + a, capture_output=True, text=True, check=True).stdout

# First matching rule wins. A marker that only says "see above" or "as above" takes the cause of
# the marker before it in the same file.
RULES = [
    ("notice", r"changed for pystachy on|each change is marked|lists them|end copy|this file is not|is copied here|changed where a|comment says"),
    ("M7 long tail", r"^\s*append\(\)"),
    ("scope cut", r"grapheme_"),
    ("UTF-8 text (#120)", r"#120|code point|whose iteration steps|utf-8|_chars|pwcs"),
    ("M4 dynamic values", r"literals and tables hold keys|was tables\.|was literals\.|for k, v in literals|is_aot|obj: mapping|obj: tuple|array_types|whose tables are written|mappingproxytype|vs1[56]_"),
    ("M1 loader, annotations", r"tuple of \d+ tuples|a tuple is indexed only|^\s*a list\s*$|list\(\)\s*$|a dict filled by loops|variable-length tuples|their types are|for the else above"),
    ("M6 stdlib", r"moved from the module level|for earthgravity|^\s*gravity"),
    ("M2 classes", r"for list\[among\]"),
    ("M7 long tail", r"iter\(|next\(|steps? `|`continue` would not"),
    ("M3 functions as values", r"imported above|for _wcwidth"),
    ("scope cut", r"image factory"),
    ("M3 functions as values", r"\bm3\b|#8\b|lambda|key=|function as a value|functions? (are|is) not (a )?values?|not a value|closure|nested function|decorat|reduce\(|\bmap\(|method=|no w\.method|alias|star\b|\*args"),
    ("M2 classes", r"inherit|subclass|base class|base\b.*left out|generic\[|__class__|type\(self\)|classes as|holds classes|values are classes|copy of basestemmer|class body"),
    ("M4 dynamic values", r"\bm4\b|#9\b|\bany\b|union|optional|may be none|\bnone\b|object\b|isinstance|mixed|rebound|rebind|keeps its argument|not rebound|narrowed"),
    ("M7 long tail", r"str\.format|\.format\(|%r|percent|\bsets?\b|set\(|frozenset|\|=|generator|yield|bytes|bytearray|#125|unsigned|\bm7\b|#12\b|slice|del of|del \w+\[|tuple indexed|only a constant indexes"),
    ("M6 stdlib", r"\bm6\b|#11\b|#129|itertools|functools|\bre\b|remagic|regex|collections|importlib|pathlib|chain|operator|warnings|\benum\b|copy\.copy|calendar|argparse|struct|math\.|datetime|namedtuple|\bfonts?\b|isatty"),
    ("M1 loader, annotations", r"\bm1\b|#6\b|#121|#116|#122|python 2|xrange|version|type_checking|startswith|quoted|#17\b"),
    ("M2 classes", r"\bm2\b|#7\b|annotat|-> ?\w|field|property|setter|declared"),
    ("scope cut", r"left out|not ported|not imported|dropped|removed|omitted|only the|pymeeus|no _languages|need"),
]

def cause(note):
    for name, pat in RULES:
        if re.search(pat, note):
            return name
    return "see above" if re.search(r"see above|as above|\(same\)|\(see", note) else "other"

def sources(spec):
    if os.path.isdir(spec):
        for dp, dn, fn in os.walk(spec):
            for f in sorted(fn):
                if f.endswith(".py"):
                    yield open(os.path.join(dp, f), encoding="utf-8").read()
        return
    for f in git("diff", "--name-only", "origin/main..." + spec).split():
        if f.startswith("ports/") and f.endswith(".py"):
            yield git("show", spec + ":" + f)


refs = sys.argv[1:] or sorted(os.path.join("ports", d) for d in os.listdir("ports") if os.path.isdir(os.path.join("ports", d)))
total, per = collections.Counter(), {}
for ref in refs:
    per[ref] = collections.Counter()
    for text in sources(ref):
        prev = "other"
        for line in text.splitlines():
            if "Pystachy port:" not in line:
                continue
            c = cause(line.split("Pystachy port:", 1)[1].lower())
            c = prev if c == "see above" else c
            prev = c
            if c != "notice":
                per[ref][c] += 1
                total[c] += 1
n = sum(total.values())
print(f"{n} markers in {len(refs)} ports")
for c, k in total.most_common():
    print(f"{k:5}  {100 * k / n:4.1f}%  {c}")
print()
for ref, cnt in sorted(per.items(), key=lambda x: sum(x[1].values())):
    print(f"{sum(cnt.values()):4}  {ref.rstrip('/').rsplit('/', 1)[-1].removeprefix('port-')}: " + ", ".join(f"{c} {k}" for c, k in cnt.most_common()))
