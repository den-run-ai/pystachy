"""Compare per-case CI times between two sets of verify artifacts (zip files).
usage: python3 -I case_times.py PATTERN_A PATTERN_B ZIP... (zip names containing PATTERN_A form set A)
Reads verify/*-times.log ("MILLISECONDS CASE") from each zip."""
import collections, re, sys, zipfile, statistics as st
pa, pb = sys.argv[1], sys.argv[2]
sets = {'A': collections.defaultdict(float), 'B': collections.defaultdict(float)}
for p in sys.argv[3:]:
    key = 'A' if pa in p else 'B' if pb in p else None
    if not key: continue
    z = zipfile.ZipFile(p)
    for n in z.namelist():
        if n.endswith('-times.log') and (len(sys.argv) < 0 or True):
            for line in z.read(n).decode().splitlines():
                f = line.split()
                if len(f) == 2 and f[0].isdigit():
                    sets[key][f[1]] += int(f[0]) / 1000
A, B = sets['A'], sets['B']
common = set(A) & set(B)
onlyA, onlyB = set(A) - set(B), set(B) - set(A)
def tot(d, ks): return sum(d[k] for k in ks)
print(f"A: {len(A)} cases {tot(A, A):.0f}s   B: {len(B)} cases {tot(B, B):.0f}s   ratio {tot(B,B)/tot(A,A):.3f}")
print(f"common {len(common)}: A {tot(A, common):.0f}s -> B {tot(B, common):.0f}s  ratio {tot(B, common)/tot(A, common):.3f}")
print(f"only A {len(onlyA)}: {tot(A, onlyA):.0f}s ; only B (new) {len(onlyB)}: {tot(B, onlyB):.0f}s, mean {tot(B, onlyB)/max(1,len(onlyB)):.2f}s vs common mean B {tot(B, common)/len(common):.2f}s")
kind = lambda c: 'errors' if c.startswith('tests/errors/') else 'deviations' if c.startswith('tests/deviations/') else 'programs'
for k in ('programs', 'errors', 'deviations'):
    ks = [c for c in common if kind(c) == k]
    if ks: print(f"  common {k:10} n={len(ks):5} A {tot(A, ks):7.0f}s B {tot(B, ks):7.0f}s ratio {tot(B, ks)/max(1e-9, tot(A, ks)):.3f}")
    ks = [c for c in onlyB if kind(c) == k]
    if ks: print(f"  new    {k:10} n={len(ks):5}            B {tot(B, ks):7.0f}s mean {tot(B, ks)/len(ks):.2f}s")
area = lambda c: c.split('/')[2] if c.startswith('tests/programs/') else kind(c)
agg = collections.defaultdict(lambda: [0, 0.0, 0.0, 0, 0.0])
for c in common:
    a = agg[area(c)]; a[0] += 1; a[1] += A[c]; a[2] += B[c]
for c in onlyB:
    a = agg[area(c)]; a[3] += 1; a[4] += B[c]
print("area: common n, A s, B s, delta s | new n, new s  (sorted by total growth)")
rows = sorted(agg.items(), key=lambda kv: -((kv[1][2] - kv[1][1]) + kv[1][4]))
for name, (n, a, b, nn, nb) in rows[:18]:
    print(f"  {name:22} {n:5} {a:7.0f} {b:7.0f} {b-a:+7.0f} | {nn:4} {nb:6.0f}")
d = sorted(common, key=lambda c: -(B[c] - A[c]))
print("largest per-case increases (common):")
for c in d[:15]: print(f"  {A[c]:7.1f} -> {B[c]:7.1f}  {c}")
print("largest new cases:")
for c in sorted(onlyB, key=lambda c: -B[c])[:12]: print(f"  {B[c]:7.1f}  {c}")
r = [B[c] / A[c] for c in common if A[c] > 0.5]
print(f"median per-case ratio (A>0.5s): {st.median(r):.3f}; quartiles {st.quantiles(r, n=4)}")
