"""Group first compiler errors of rejected CPython test methods by what removing them needs.

usage: python3.13 -I groups.py METHODS.json   (classify.py from ../scripts on sys.path)
'compile': class-model, inference or match features a static compiler can implement;
'library': a missing module or name; 'reflect': runtime reflection or dynamic semantics.
The first matching row wins; the rest stay unassigned. Only the first error is visible.
"""
import collections, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from classify import group  # noqa: E402

GROUPS = [
    ("compile", "local classes (class inside a function)", r"a class inside a function"),
    ("compile", "field / class-attribute types not inferred", r"cannot infer the type of (field|class attribute)"),
    ("compile", "empty containers not inferred", r"cannot infer the type of (an empty|'[^']*', an empty)"),
    ("compile", "class-body statements (nested class, augassign...)", r"a class body may only contain"),
    ("compile", "builtin base classes (set/frozenset/bytes...)", r"unsupported base class"),
    ("compile", "inheritance from generic class templates", r"inheritance with generic class templates"),
    ("compile", "multiple inheritance", r"multiple inheritance requires"),
    ("compile", "match patterns (mapping, starred, class, non-tuple subjects, complex)", r"patterns are not supported|patterns require"),
    ("library", "enum.member / enum.verify / STRICT", r"from 'enum'"),
    ("library", "gc module (collect, is_tracked, thresholds)", r"there is no gc\.py"),
    ("library", "inspect module (mostly cleandoc)", r"there is no inspect\.py"),
    ("reflect", "pickle / copyreg / marshal", r"there is no (pickle|copyreg|marshal)\.py"),
    ("reflect", "eval / exec / compile, ast, dis", r"unsupported call (compile|eval|exec)\(|there is no (ast|dis)\.py"),
    ("library", "other missing modules (configparser, decimal, _pyio, locale, ...)", r"is not a builtin module"),
    ("reflect", "modules or classes as values", r"cannot be used as a value"),
    ("reflect", "str.format of a computed format string", r"str\.format\(\) of a format string computed"),
    ("reflect", "exception attributes (__context__, __traceback__, args)", r"the attributes of an exception"),
]
recs = [r for r in json.load(open(sys.argv[1]))["records"] if r["status"] == "compile-error"]
count, lang, files = collections.Counter(), collections.Counter(), collections.defaultdict(set)
for r in recs:
    for kind, name, pat in GROUPS:
        if re.search(pat, r.get("detail", "")):
            count[(kind, name)] += 1
            files[(kind, name)].add(r["file"])
            lang[(kind, name)] += group(r["file"]) == "language"
            break
totals = collections.Counter()
for (kind, name), n in count.most_common():
    totals[kind] += n
    print(f"{kind:8s} {n:5d}  language {lang[(kind, name)]:4d}  files {len(files[(kind, name)]):3d}  {name}")
print(dict(totals), "of", len(recs), "rejected; unassigned", len(recs) - sum(count.values()))
