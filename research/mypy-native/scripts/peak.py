import os, subprocess, sys, time, threading
t = time.time()
p = subprocess.Popen(sys.argv[1:])
peak = 0
def children(pid):
    out = [pid]
    try:
        for tid in os.listdir(f"/proc/{pid}/task"):
            with open(f"/proc/{pid}/task/{tid}/children") as f:
                for c in f.read().split():
                    out += children(int(c))
    except OSError:
        pass
    return out
while p.poll() is None:
    tot = 0
    for c in children(p.pid):
        try:
            with open(f"/proc/{c}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        tot += int(line.split()[1])
        except OSError:
            pass
    peak = max(peak, tot)
    time.sleep(0.05)
print(f"exit={p.returncode} wall={time.time() - t:.1f}s peak_rss_tree={peak / 1024:.0f} MiB", file=sys.stderr)
