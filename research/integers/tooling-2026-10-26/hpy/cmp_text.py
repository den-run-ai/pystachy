"""Compare the edited mpz core's parsing and decimal formatting with CPython's int.
usage: python3 -I cmp_text.py DRIVER N SEED"""
import random, subprocess, sys

driver, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(seed)
DIG = "0123456789abcdefghijklmnopqrstuvwxyz"

def rand_digits(base, count):
    s = []
    for i in range(count):
        d = DIG[rnd.randrange(base)]
        s.append(d.upper() if rnd.random() < 0.3 else d)
        if i + 1 < count and rnd.random() < 0.1:
            s.append("_")
    return "".join(s)

def rand_text():
    base = rnd.choice([0, 10, 10, 2, 3, 4, 7, 8, 16, 32, 36, rnd.randrange(2, 37)])
    count = rnd.choice([1, 2, 8, 9, 10, 17, 18, 19, 100, 1000, 4299, 4300, 4301, rnd.randrange(1, 6000)])
    eb = base or 10
    prefix = ""
    if base in (0, 16) and rnd.random() < 0.3: prefix, eb = rnd.choice(["0x", "0X"]), 16
    elif base in (0, 8) and rnd.random() < 0.3: prefix, eb = rnd.choice(["0o", "0O"]), 8
    elif base in (0, 2) and rnd.random() < 0.3: prefix, eb = rnd.choice(["0b", "0B"]), 2
    if prefix and rnd.random() < 0.3: prefix += "_"
    body = rand_digits(eb, count)
    if base == 0 and not prefix and rnd.random() < 0.2: body = "0" * rnd.randrange(1, 4) + body
    sign = rnd.choice(["", "", "-", "+"])
    ws = lambda: rnd.choice(["", "", " ", "\t", "  \t "])
    text = ws() + sign + prefix + body + ws()
    if rnd.random() < 0.05:   # make it invalid somewhere
        k = rnd.randrange(len(text) + 1)
        text = text[:k] + rnd.choice(["_", "__", "z", "!", " ", "-"]) + text[k:]
    return base, text

lines, expect = [], []
for _ in range(n):
    kind = rnd.random()
    if kind < 0.5:
        base, text = rand_text()
        lines.append(f"P {base} {text}")
        try:
            v = int(text, base)
            expect.append(("ok", format(v, "x") if v >= 0 else "-" + format(-v, "x")))
        except ValueError as e:
            expect.append(("err", str(e)))
    else:
        bits = rnd.choice([1, 29, 30, 31, 59, 60, 61, 64, 100, 1000, 14284, 14285, 14286, rnd.randrange(1, 15000)])
        v = rnd.getrandbits(bits) | (1 << (bits - 1)) if rnd.random() < 0.8 else rnd.getrandbits(bits)
        if rnd.random() < 0.15:
            v = rnd.choice([10 ** 4299, 10 ** 4300 - 1, 10 ** 4300, 10 ** 9, 10 ** 9 - 1, 10 ** 18, 2 ** 30, 0])
        if rnd.random() < 0.5: v = -v
        lines.append("F " + (format(v, "x") if v >= 0 else "-" + format(-v, "x")))
        try:
            expect.append(("ok", str(v)))
        except ValueError as e:
            expect.append(("err", str(e)))
out = subprocess.run([driver], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True).stdout.splitlines()
assert len(out) == len(lines), (len(out), len(lines))
bad = 0
for line, (kind, want), got in zip(lines, expect, out):
    if kind == "ok":
        ok = got == want
    else:
        # literal errors: any error (the harness formats badlit differently); limit errors: same text
        ok = got.startswith("E ") and ("Exceeds the limit" not in want or got[2:] == "ValueError: " + want)
    if not ok:
        bad += 1
        if bad <= 10:
            print("MISMATCH", repr(line[:120]), "want", kind, repr(want[:120]), "got", repr(got[:120]))
print(f"{len(lines)} cases, {bad} mismatches, {sum(k == 'err' for k, _ in expect)} expected errors")
sys.exit(1 if bad else 0)
