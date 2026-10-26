"""Compare the edited mpz core's +, -, *, //, % and squares with CPython's int.
usage: python3 -I cmp_arith.py DRIVER N SEED"""
import random, subprocess, sys

driver, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(seed)

def operand():
    limbs = rnd.choice([1, 2, 3, 69, 70, 71, 72, 139, 140, 141, 142, 210, 280, 281, 500, 700, 1000,
                        rnd.randrange(1, 100), rnd.randrange(60, 400), rnd.randrange(1, 3000)])
    bits = 30 * limbs - rnd.randrange(30)
    kind = rnd.random()
    if kind < 0.15:
        v = (1 << bits) - 1                      # solid ones: maximal carries
    elif kind < 0.25:
        v = 1 << (bits - 1) | rnd.getrandbits(rnd.randrange(1, 64))   # sparse
    elif kind < 0.35:                            # long runs of ones and zeros
        v, b = 0, 0
        while b < bits:
            run = min(rnd.randrange(1, 200), bits - b)
            v = v << run | ((1 << run) - 1 if rnd.random() < 0.5 else 0)
            b += run
        v |= 1 << (bits - 1)
    else:
        v = rnd.getrandbits(bits) | 1 << (bits - 1)
    return -v if rnd.random() < 0.5 else v

hx = lambda v: format(v, "x") if v >= 0 else "-" + format(-v, "x")
lines, want = [], []
for _ in range(n):
    a = operand()
    r = rnd.random()
    if r < 0.3:
        lines.append("S " + hx(a)); want.append(hx(a * a))
    else:
        b = operand() if rnd.random() < 0.85 else (a if rnd.random() < 0.5 else -a)
        op = rnd.choice([0, 1, 2, 2, 2, 3, 4])
        if op == 3 and b == 0 or op == 4 and b == 0:
            op = 2
        lines.append(f"M {op} {hx(a)} {hx(b)}")
        want.append(hx([a + b, a - b, a * b, a // b if b else 0, a % b if b else 0][op]))
out = subprocess.run([driver], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True).stdout.splitlines()
bad = sum(1 for w, g in zip(want, out) if w != g) + abs(len(out) - len(want))
for line, w, g in zip(lines, want, out):
    if w != g:
        print("MISMATCH", line[:80], "want", w[:60], "got", g[:60]); break
print(f"{len(lines)} cases, {bad} mismatches")
sys.exit(1 if bad else 0)
