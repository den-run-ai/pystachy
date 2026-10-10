import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spikemod as m

class SlowOut:                       # a sys.stdout whose write() releases the GIL (Pys -> Py callback)
    def __init__(self, real): self.real = real
    def write(self, s):
        time.sleep(0.001)
        return self.real.write(s)
    def flush(self): self.real.flush()

want = 20 * (3 * 1 + 2 * 2 + 1 * 3)
bad = []
def worker():
    for _ in range(300):
        if m.total("x yy zzz x yy x " * 20) != want:
            bad.append(1)
sys.stdout = SlowOut(sys.__stdout__)
th = threading.Thread(target=worker); th.start()
for i in range(100):
    m.hello(str(i) * 10)             # compiled frames live while another thread enters
th.join()
sys.stdout = sys.__stdout__
print("wrong results:", len(bad))
