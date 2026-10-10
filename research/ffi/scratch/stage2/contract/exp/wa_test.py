# Two threads run a compiled with-block that calls out to Python (print -> a sys.stdout.write
# that sleeps, so the GIL changes hands) while the block's unwind action (close the file) is live.
# Thread R raises after the call-out (its landing pad runs unwind actions down to its mark);
# thread N writes after the call-out and must find its own file still open.
import os, sys, threading, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spikemod as m

class SlowOut:
    def __init__(self, real): self.real = real
    def write(self, s):
        time.sleep(0.0005)
        return self.real.write(s)
    def flush(self): self.real.flush()

res = {"r": [], "n": []}
def run(kind, k):
    for i in range(k):
        res[kind].append(m.wa(kind + str(i % 7)))
sys.stdout = SlowOut(open(os.devnull, "w"))
ts = [threading.Thread(target=run, args=("r", 200)), threading.Thread(target=run, args=("n", 200))]
for t in ts: t.start()
for t in ts: t.join()
sys.stdout = sys.__stdout__
bad_r = sum(1 for x in res["r"] if x != 2); bad_n = sum(1 for x in res["n"] if x != 1)
print("sample n:", res["n"][:8], "files:", sorted(set(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"files","wa_n"+str(i))).read() for i in range(7))));print("raising thread wrong:", bad_r, " plain thread wrong:", bad_n)
