"""Supplemental constructor review; does not alter the raw audit classification.

Resolve numbered immutable strings and TBAA references by their complete contents,
and map only demonstrated same-layout template-to-nominal names. All remaining
function differences are retained for manual review. This is not a semantic proof.
"""
import difflib
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
ROWS = json.loads((ROOT / "constructor-review-cases.json").read_text())


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def functions(text):
    result = {}
    current = None
    for line in text.splitlines(keepends=True):
        found = re.match(r"define[^@]*@([^\n(]+)\(", line)
        if found:
            current = found[1]
            result[current] = line
        elif current is not None:
            result[current] += line
            if line.strip() == "}":
                current = None
    return result


def names(text, mapping):
    for before, after in sorted(mapping.items(), key=lambda x: -len(x[0])):
        text = text.replace(before, after)
    return text


def canonical(text, classmap, functionmap):
    text = names(text, classmap)
    strings = dict(re.findall(r"^(@s\.[0-9]+) = (.*)$", text, re.M))
    strings = {name: "@str_" + digest(value) for name, value in strings.items()}
    metas = dict(re.findall(r"^(![0-9]+) = (.*)$", text, re.M))
    resolved = {}

    def meta(name):
        if name not in resolved:
            assert name in metas, name
            expanded = re.sub(r"![0-9]+", lambda m: meta(m[0]), metas[name])
            resolved[name] = "!meta_" + digest(expanded)
        return resolved[name]

    output = {}
    for key, value in functions(text).items():
        key = functionmap.get(key, key)
        value = re.sub(r"@[A-Za-z0-9_$.\-]+", lambda m: "@" + functionmap.get(m[0][1:], m[0][1:]), value)
        value = re.sub(r"@s\.[0-9]+", lambda m: strings[m[0]], value)
        value = re.sub(r"![0-9]+", lambda m: meta(m[0]), value)
        output[key] = value
    return output


out = []
for row in ROWS:
    if row["declarations_only"] or row["number"] in (85, 86, 110, 975, 1162, 2114, 2117):
        continue
    directory = ROOT / row["directory"]
    old = (directory / "old.location-normalized.ll").read_text()
    new = (directory / "new.location-normalized.ll").read_text()
    oldtypes = dict(re.findall(r"^%C\.([^ ]+) = type (.*)$", old, re.M))
    newtypes = dict(re.findall(r"^%C\.([^ ]+) = type (.*)$", new, re.M))
    classmap = {name: name[:-2] for name, value in oldtypes.items()
                if name.endswith("-1") and name[:-2] in newtypes and newtypes[name[:-2]] == value}
    oldrenamed = names(old, classmap)
    oldfunctions, newfunctions = functions(oldrenamed), functions(new)
    functionmap = {name: name[:-2] for name in oldfunctions if name not in newfunctions
                   and name.endswith(".1") and name[:-2] in newfunctions}
    left, right = canonical(old, classmap, functionmap), canonical(new, {}, {})
    residual = [name for name in sorted(left.keys() | right.keys()) if left.get(name) != right.get(name)]
    text = ""
    for name in residual:
        text += "\nFUNCTION " + name + "\n"
        text += "".join(difflib.unified_diff(left.get(name, "").splitlines(keepends=True),
                                              right.get(name, "").splitlines(keepends=True),
                                              fromfile="old", tofile="new"))
    (directory / "constructor.residual.diff").write_text(text)
    out.append({"number": row["number"], "case": row["case"], "class_mapping": classmap,
                "method_mapping": functionmap, "equal_functions": len(left.keys() & right.keys()) - len(residual),
                "residual_functions": residual, "residual_diff": str(directory / "constructor.residual.diff")})
(ROOT / "constructor-mechanical.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps(out, indent=2))
