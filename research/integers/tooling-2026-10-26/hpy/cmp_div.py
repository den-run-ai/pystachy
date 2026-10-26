"""Division-focused comparison of the edited mpz core with CPython: divisor top digits of
every bit length (every normalization shift), one-digit divisors, quotients of one digit up to
thousands, and Knuth D's add-back cases. usage: python3 -I cmp_div.py DRIVER N SEED"""
import random, subprocess, sys
driver, n, seed = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
rnd = random.Random(seed)
hx = lambda v: format(v, "x") if v >= 0 else "-" + format(-v, "x")
lines, want = [], []
for _ in range(n):
    bl = rnd.choice([1, 2, 3, 5, 30, 70, 141, rnd.randrange(1, 400)])      # divisor digits
    top_bits = rnd.randrange(1, 31)                                          # its top digit's bit length
    b = (rnd.getrandbits(top_bits - 1) | 1 << (top_bits - 1)) << (30 * (bl - 1))
    pat = rnd.random()
    if pat < 0.3:
        b |= rnd.getrandbits(30 * (bl - 1)) if bl > 1 else 0
    elif pat < 0.5 and bl > 1:
        b |= (1 << (30 * (bl - 1))) - 1                                     # all ones below the top
    q = rnd.getrandbits(rnd.choice([1, 29, 30, 31, 60, 300, 30 * rnd.randrange(1, 300)]))
    if rnd.random() < 0.2:
        q = (1 << (30 * rnd.randrange(1, 50))) - 1                           # quotient digits BASE-1
    r = rnd.randrange(b) if rnd.random() < 0.8 else rnd.choice([0, b - 1])
    a = q * b + r
    if rnd.random() < 0.1:
        a = rnd.randrange(b)                                                 # |a| < |b|
    sa, sb = rnd.choice([1, -1]), rnd.choice([1, -1])
    a, b = sa * a, sb * b
    op = rnd.choice([3, 4])
    lines.append(f"M {op} {hx(a)} {hx(b)}")
    want.append(hx(a // b if op == 3 else a % b))
out = subprocess.run([driver], input="\n".join(lines) + "\n", capture_output=True, text=True, check=True).stdout.splitlines()
bad = sum(1 for w, g in zip(want, out) if w != g) + abs(len(out) - len(want))
for line, w, g in zip(lines, want, out):
    if w != g:
        print("MISMATCH", line[:100], "want", w[:60], "got", g[:60]); break
print(f"{len(lines)} cases, {bad} mismatches")
sys.exit(1 if bad else 0)
