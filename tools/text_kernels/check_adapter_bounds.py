#!/usr/bin/env python3
"""Independent protected-page checks of the exact optional adapter shared library."""
import argparse
import ctypes
import hashlib
import json
import mmap
from pathlib import Path
import random


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    lib = ctypes.CDLL(str(args.library.resolve()))
    scan = lib.pystachy_stringzilla_json_scan
    scan.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    scan.restype = ctypes.c_int64
    lib.pystachy_stringzilla_backend.restype = ctypes.c_char_p
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.mprotect.restype = ctypes.c_int
    page = mmap.PAGESIZE
    if page < 4096:
        raise ValueError("guard cases require a page of at least 4096 bytes")
    buf = mmap.mmap(-1, 3 * page)
    anchor = ctypes.c_char.from_buffer(buf)
    base = ctypes.addressof(anchor)
    if libc.mprotect(base, page, 0) or libc.mprotect(base + 2 * page, page, 0):
        raise OSError(ctypes.get_errno(), "mprotect guards")
    stops = sorted(set(range(32)) | {34, 92})
    rng = random.Random(65530)
    checks = 0
    lengths = list(range(260)) + [511, 512, 513, 1023, 1024, 1025, 2047, 2048, 2049, 4095, 4096]
    try:
        for n in lengths:
            data = bytes(rng.choice([33, 35, 65, 127, 128, 194, 233, 255]) for _ in range(n))
            ptr = base + 2 * page - n
            ctypes.memmove(ptr, data, n)
            if scan(ptr, n) != n:
                raise AssertionError((n, "miss"))
            checks += 1
            if n:
                for pos in sorted({0, min(1, n - 1), n // 2, n - 1}):
                    for stop in stops:
                        trial = data[:pos] + bytes([stop]) + data[pos + 1:]
                        ctypes.memmove(ptr, trial, n)
                        actual = scan(ptr, n)
                        if actual != pos:
                            raise AssertionError((n, pos, stop, actual))
                        checks += 1
        result = {"backend": lib.pystachy_stringzilla_backend().decode(),
                  "adapter_sha256": hashlib.sha256(args.library.read_bytes()).hexdigest(),
                  "guard_page_cases": checks, "lengths": len(lengths), "max_length": max(lengths),
                  "seed": 65530, "passed": True}
        args.output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))
    finally:
        if libc.mprotect(base, page, 3) or libc.mprotect(base + 2 * page, page, 3):
            raise OSError(ctypes.get_errno(), "mprotect restore")
        del anchor
        buf.close()


if __name__ == "__main__":
    main()
