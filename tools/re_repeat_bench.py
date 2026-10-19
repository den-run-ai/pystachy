"""Repeated-character-class regex microbenchmark, valid CPython and Pystachy.

Usage: python3 tools/re_repeat_bench.py [loops] [--cpu]
       ./pystachy build tools/re_repeat_bench.py -o /tmp/re_repeat_bench
       /tmp/re_repeat_bench [loops] [--cpu]

Default: 20 loops per sample, three samples per case. Printed seconds are the
median in-process time for one sample; they exclude startup, regex compilation,
input construction, warm-up and the content checksum. --cpu uses process time
instead of wall time. Compare checksums before comparing timings, and run paired
old/new AOT binaries on an otherwise idle host. Increase loops for short samples.

Long runs isolate repeat counting; dense and sparse matches expose search/result
costs. Lazy, finite and possessive repeats exercise different VM paths. Unicode
inputs include Kelvin sign, long s and non-ASCII accented/Greek case pairs. Plain
controls help separate ignore-case gains from unrelated changes.
"""
import re
import sys
import time


def bench(name: str, pattern: str, flags: int, source: str, loops: int, cpu: bool) -> None:
    compiled = re.compile(pattern, flags)
    # Warm the engine and retain a content-sensitive, deterministic checksum.
    matches = compiled.findall(source)
    content_check = 0
    for i in range(len(matches)):
        match = matches[i]
        content_check += (i + 1) * (len(match) + ord(match[0]) + ord(match[-1]))
    samples: list[float] = []
    count_check = 0
    for _ in range(3):
        start = time.process_time() if cpu else time.perf_counter()
        for _ in range(loops):
            count_check += len(compiled.findall(source))
        elapsed = (time.process_time() if cpu else time.perf_counter()) - start
        samples.append(elapsed)
    samples.sort()
    print(f"{name:24} seconds {samples[1]:.6f} checksum {content_check} count {count_check}")


def main() -> None:
    loops = 20
    cpu = False
    for arg in sys.argv[1:]:
        if arg == "--cpu":
            cpu = True
        else:
            loops = int(arg)
    if loops < 1:
        raise ValueError("loops must be positive")
    print("loops", loops, "samples", 3, "clock", "cpu" if cpu else "wall")

    ascii_long = "AbCdEf_" * 128 + "!"
    unicode_long = "Ab\u212a\u017f\u00e9\u00c9\u03c3\u03a3_" * 96 + "!"
    ascii_dense = "Ab!cD?E_9" * 96
    unicode_dense = "\u212a\u017f!\u00e9\u00c9?\u03c3\u03a3_9" * 96
    ascii_sparse = "0123456789!?" * 64 + "AbCd_" + "0123456789!?" * 64
    unicode_sparse = "0123456789!?" * 64 + "\u212a\u017f\u00e9\u03a3_" + "0123456789!?" * 64
    ascii_flags = re.IGNORECASE | re.ASCII
    unicode_flags = re.IGNORECASE
    ascii_class = "[A-Z_]"
    unicode_class = "[A-Z_\u00c9\u03a3]"

    bench("ascii-ignore-greedy", ascii_class + "+", ascii_flags, ascii_long, loops, cpu)
    bench("ascii-ignore-finite", ascii_class + "{2,32}", ascii_flags, ascii_long, loops, cpu)
    bench("ascii-ignore-lazy", ascii_class + "{2,32}?", ascii_flags, ascii_long, loops, cpu)
    bench("ascii-ignore-possessive", ascii_class + "++", ascii_flags, ascii_long, loops, cpu)
    bench("ascii-ignore-dense", ascii_class + "+", ascii_flags, ascii_dense, loops, cpu)
    bench("ascii-ignore-sparse", ascii_class + "+", ascii_flags, ascii_sparse, loops, cpu)
    bench("unicode-ignore-greedy", unicode_class + "+", unicode_flags, unicode_long, loops, cpu)
    bench("unicode-ignore-finite", unicode_class + "{2,32}", unicode_flags, unicode_long, loops, cpu)
    bench("unicode-ignore-lazy", unicode_class + "{2,32}?", unicode_flags, unicode_long, loops, cpu)
    bench("unicode-ignore-possessive", unicode_class + "++", unicode_flags, unicode_long, loops, cpu)
    bench("unicode-ignore-dense", unicode_class + "+", unicode_flags, unicode_dense, loops, cpu)
    bench("unicode-ignore-sparse", unicode_class + "+", unicode_flags, unicode_sparse, loops, cpu)
    bench("ascii-plain-greedy", "[A-Za-z_]+", 0, ascii_long, loops, cpu)
    bench("ascii-plain-dense", "[A-Za-z_]+", 0, ascii_dense, loops, cpu)
    bench("unicode-plain-greedy", "[A-Za-z_\u212a\u017f\u00e9\u00c9\u03c3\u03a3]+", 0, unicode_long, loops, cpu)
    bench("unicode-plain-dense", "[A-Za-z_\u212a\u017f\u00e9\u00c9\u03c3\u03a3]+", 0, unicode_dense, loops, cpu)


if __name__ == "__main__":
    main()
