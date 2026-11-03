# #127: chevron's tokenizer loop, cutting a template at each "{{" (find + slice, or split)
import sys
import time


def main() -> None:
    mode = sys.argv[1]
    reps = int(sys.argv[2])
    units = int(sys.argv[3])
    base = "abcdefghij{{x}}" * units
    n = 0
    t0 = time.perf_counter()
    for rep in range(reps):
        t = base
        while t:
            if mode == "split":
                parts = t.split("{{", 1)
                t = parts[1] if len(parts) == 2 else ""
            else:
                i = t.find("{{")
                t = t[i + 2:] if i >= 0 else ""
            n += 1
    print(mode, len(base), n)
    print("TIME", time.perf_counter() - t0, file=sys.stderr)


main()
