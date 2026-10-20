# Lines of malformed UTF-8 from stdin, which Pystachy keeps as bytes and CPython (in UTF-8 mode)
# reads as lone surrogates, one character per byte that begins none: widths, padding, precision,
# zfill, expandtabs and % count characters as len() does, and print the bytes back
import sys

for line in sys.stdin:
    s = line.rstrip("\n")
    print(len(s), len(f"{s:>8}"), len(s.center(9)), len(s.ljust(7, "*")), len(s.rjust(7)), len(s.zfill(8)))
    print(f"[{s:>8}]", f"[{s:^9}]", f"[{s:.2}]", f"[{s:*<7.3}]", f"[{s.zfill(8)}]")
    print(len((s + "\t|").expandtabs(8)), (s + "\tx").expandtabs(4) + "|")
    print("%-6s|%6s|%.3s|" % (s, s, s))
    try:
        print(format(5, s))
    except ValueError as e:
        print("ValueError", e)
