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
    print("owned", state.s == codes, state.offs == offs, state.s is not re._last_codes)
