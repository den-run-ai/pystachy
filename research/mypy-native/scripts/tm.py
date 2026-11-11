"""Run a command; print wall seconds and the peak RSS of its process tree's largest child (MiB)."""
import resource, subprocess, sys, time
t = time.monotonic()
r = subprocess.run(sys.argv[1:])
dt = time.monotonic() - t
rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
print(f"TIME {dt:.2f} s  PEAK {rss:.0f} MiB  rc={r.returncode}", file=sys.stderr)
sys.exit(r.returncode)
