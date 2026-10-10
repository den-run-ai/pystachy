import sys
sys.path.insert(0, sys.argv[1])
import ss
for good in (1, 0):
    res = []
    for seed in range(1, 201):
        res.append(ss.run(good, seed * 7919, lambda: ss.scan()))
    sect = sum(r[0] for r in res); full = sum(r[1] for r in res)
    print("callout_good" if good else "callout_naive", "found in Pystachy sections only:", sect, "/200; in the whole stack:", full, "/200")
