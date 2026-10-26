# usage: irfuncs.py OLD.ll NEW.ll -> names of functions whose bodies differ, after naming each
# string constant @s.N by its contents (a new constant renumbers every later one)
import re, sys

SREF = re.compile(r"@s\.(\d+)\b")

def load(path):
    text = open(path, encoding="utf-8", errors="replace").read().split("\n")
    strs = {}
    for line in text:
        m = re.match(r'@s\.(\d+) = .*c"(.*)\\00"\}', line)
        if m:
            strs[m.group(1)] = m.group(2)
    def norm(s):
        return SREF.sub(lambda m: "@s<" + strs.get(m.group(1), "?" + m.group(1)) + ">", s)
    funcs = {}
    others = []
    name = None
    body = []
    for line in text:
        if line.startswith("define "):
            m = re.search(r"@([^(]+)\(", line)
            name = m.group(1) if m else line
            body = [norm(line)]
        elif name is not None:
            body.append(norm(line))
            if line.startswith("}"):
                funcs[name] = "\n".join(body)
                name = None
        elif not line.startswith("@s."):
            others.append(norm(line))
    return funcs, sorted(strs.values()), others

fa, sa, oa = load(sys.argv[1])
fb, sb, ob = load(sys.argv[2])
for k in sorted(set(fa) | set(fb)):
    if fa.get(k) != fb.get(k):
        print(("changed " if k in fa and k in fb else "only-old " if k in fa else "only-new ") + k)
if sa != sb:
    print("strings " + repr(sorted(set(sb) - set(sa)))[:300] + " added, " + repr(sorted(set(sa) - set(sb)))[:300] + " removed")
if sorted(oa) != sorted(ob):
    print("other-globals differ")
