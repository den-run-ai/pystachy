# lib/re caches the last subject's code points (re._last_codes, absent in CPython) for the next
# call on it. Unbounded findall()/finditer(), split(), sub() and subn() read the subject to its end, so they
# release a cache that they filled for a subject longer than re._KEEP bytes (1 MB, lowered here):
# its decoding does not outlive the call (#589). A cache that was there before, as match(s, pos)
# loops fill it, stays. An operation keeps its own decoded lists, also while a sub() callback
# matches the same or another long subject, and matches stay usable once the cache is gone.
import re

re._KEEP = 64
short = "ab1 cd22 ef333"
edge = "ab1 cd22 ef333 " * 4 + "ghij"  # (exactly re._KEEP bytes: kept)
long = "ab1 cd22 ef333 " * 10
wide = "é1 Ω22 𝔄333 " * 10  # (not ASCII: the cache also holds each code point's byte offset)
word = re.compile(r"[^\W\d]+")
num = re.compile(r"(\d)\d*")


def state(s: str) -> str:
    if re._last is s:
        return "cached %d %d" % (len(re._last_codes), len(re._last_offs))
    return "released %s %d %d" % (re._last == "", len(re._last_codes), len(re._last_offs))


def run(k: int, s: str) -> str:
    if k == 0:
        return str(word.findall(s)[:3])
    if k == 1:
        return str([m.span() for m in num.finditer(s)][:3])
    if k == 2:
        return str(num.split(s, 2)[:4])
    if k == 3:
        return str(num.sub("#", s).split()[:3])
    return str(num.subn("<\\1>", s)[1])


for name, s in [("short", short), ("edge", edge), ("long", long), ("wide", wide)]:
    for k in range(5):
        re.purge()
        first = run(k, s)
        after = state(s)
        before = re._decoded
        again = run(k, s)
        print(name, k, first, after, again == first, re._decoded - before)

# A cache that a search(s, pos) loop filled stays through findall() and sub(), which reuse it.
re.purge()
pos = 0
n = 0
while pos < len(long):
    m = word.search(long, pos)
    if m is None:
        break
    n += 1
    pos = m.end()
before = re._decoded
print("scanner", n, len(num.findall(long)), num.sub("", long)[:10], state(long), re._decoded == before)


# Bounded findall()/finditer() windows need the same geometrically growing prefix cache as
# search(). Non-ASCII windows can start/end inside a UTF-8 character; the numeric matches still
# have one byte each, and cache retention uses the normalized byte endpos, not a code-point index.
for subject in [long, wide]:
    for k in range(2):
        re.purge()
        before = re._decoded
        n = 0
        for pos in range(len(subject)):
            if k == 0:
                n += len(num.findall(subject, pos, pos + 1))
            else:
                n += len(num.finditer(subject, pos, pos + 1))
        print("windows", k, n, re._decoded - before <= 3 * len(subject), re._last is subject)


# In a sub() callback, sub() on another long subject releases its decoding, findall() on long then
# decodes and releases lists of its own, and search() decodes long again; after a purge(), split()
# decodes and releases its own. The outer substitution goes on with the code points it decoded.
def nest(m: re.Match) -> str:
    other = num.sub("#", wide)
    inner = num.findall(long)
    after = num.search(long, 3)
    return "[%s %d %d %s]" % (m.group(), len(inner), other.count("#"), "-" if after is None else str(after.group(1)))


def purging(m: re.Match) -> str:
    re.purge()
    return str(len(word.split(long))) + m.group()


for subject in [long, wide]:
    re.purge()
    print("nested", word.sub(nest, subject).split()[:6], state(subject))
    re.purge()
    print("purged", num.sub(purging, subject).split()[:3], state(subject))

# Matches from a released subject keep their spans and groups.
re.purge()
found = [m for m in num.finditer(wide)]
print("matches", state(wide), len(found), found[0].span(), found[1].group(1), found[-1].start(1), found[-1].group())
