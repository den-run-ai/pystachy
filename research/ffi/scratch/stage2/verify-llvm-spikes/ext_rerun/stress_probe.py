import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spikemod as m
t0 = time.perf_counter()
ok = all(m.total("x yy zzz x yy x " * 20) == 200 for _ in range(2000))
print("ok:", ok, f"{(time.perf_counter()-t0)*1e3:.1f} ms for 2000 calls")
