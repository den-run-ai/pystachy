# _decoded is the port's deterministic work counter, absent in CPython. A fixed endpos must
# decode bounded work even as the subject grows; increasing bounds must remain linear overall.
import re

rx = re.compile(".")
for n in [10, 100, 1000, 10000]:
    for unit in ["a", "é", "𝔄"]:
        subject = unit * n
        re.purge()
        before = re._decoded
        m = rx.match(subject, 0, len(unit))
        print("bounded", n, unit, m is not None and m.group() == unit, re._decoded - before <= 2)
        before = re._decoded
        rx.search(subject, 0, len(unit))
        print("reuse", re._decoded == before)

for unit in ["a", "é", "𝔄"]:
    subject = unit * 100
    re.purge()
    before = re._decoded
    for end in range(1, len(subject) + 1):
        rx.match(subject, 0, end)
    print("growing", unit, re._decoded - before <= 4 * len(subject))
    # The completed whole-subject cache serves all smaller bounds without decoding again.
    before = re._decoded
    for end in range(0, len(subject) + 1):
        rx.match(subject, 0, end)
    print("full reuse", re._decoded == before)

    re.purge()
    state = rx._state(subject, 0, len(unit))
    codes = state.s.copy()
    offs = state.offs.copy()
    rx.match(subject, 0, len(subject))
    # (a subject whose bytes are its code points is read in place: the match leaves the cache that
    # _state made, which is still the state's)
    print("owned", state.s == codes, state.offs == offs, (state.s is re._last_codes) == (unit == "a"))

# A failed required ASCII prefix needs no matcher state, even on a Unicode subject.
# A matching prefix still leaves captures, bounds and case flags to the engine.
directive = re.compile(r"(\.\.)(?i:class)")
subject = ".é" * 100
re.purge()
before = re._decoded
print("prefix miss", directive.match(subject) is None, re._decoded == before)
hit = directive.match("..ClAsSé")
print("prefix match", hit.group(1) if hit else "-", directive.match("..class", 0, 3) is None)
offset = directive.match("é..class", 1)
print("prefix offset", offset.span() if offset else (-1, -1))
