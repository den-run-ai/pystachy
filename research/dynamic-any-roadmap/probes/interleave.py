# usage: interleave.py ROUNDS MODE ARG BIN... : runs each binary in turn, ROUNDS times, pinned to core 1;
# prints medians of the build and process nanoseconds each run prints (checksum first)
import statistics
import subprocess
import sys

rounds, mode, arg, bins = int(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4:]
res = {b: ([], []) for b in bins}
sums = set()
for _ in range(rounds):
    for b in bins:
        out = subprocess.run(["taskset", "-c", "1", b, mode, arg], capture_output=True, text=True, check=True).stdout.split()
        sums.add(out[0])
        res[b][0].append(int(out[1]))
        res[b][1].append(int(out[2]))
print("checksums", sums)
for b in bins:
    print(b.rsplit("/", 1)[-1], mode, arg, "build ms %.1f" % (statistics.median(res[b][0]) / 1e6), "process ms %.1f" % (statistics.median(res[b][1]) / 1e6))
