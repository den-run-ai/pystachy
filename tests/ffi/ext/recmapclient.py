# A mapping below Linux's growing main stack must bound an extension's native recursion (#1032).
# Each dangerous probe is isolated, disables core dumps and has a timeout. The CPython twin has
# heap frames and uses a low logical limit; both implementations must catch and recover.
import ctypes
import errno
from pathlib import Path
import platform
import resource
import subprocess
import sys

KIB = 1024
MIB = 1024 * KIB


def probe(mode: str) -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    hard = resource.getrlimit(resource.RLIMIT_STACK)[1]
    target = resource.RLIM_INFINITY if mode == "unlimited" else 64 * MIB
    if hard != resource.RLIM_INFINITY and (target == resource.RLIM_INFINITY or hard < target):
        print(f"SKIP {mode}: hard stack limit prevents probe")
        raise SystemExit(77)
    # The host may raise its limit after exec, before importing a native extension.
    resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
    lines = Path("/proc/self/maps").read_text().splitlines()
    stack = next(line for line in lines if line.endswith("[stack]"))
    start = int(stack.split("-", 1)[0], 16)
    page = resource.getpagesize()
    # Even on a 64 KiB-page machine there is room for the default 256-page guard gap.
    distance = max(3 * MIB, 512 * page)
    address = start - distance
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_long]
    libc.mmap.restype = ctypes.c_void_p
    libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    protection = 0 if mode == "none" else 3
    # MAP_FIXED_NOREPLACE cannot replace an existing VMA. Check the returned address too, since
    # older kernels can ignore this flag. An unsupported probe is explicit, never a claimed pass.
    mapped = libc.mmap(address, page, protection, 0x02 | 0x20 | 0x100000, -1, 0)
    if mapped != address:
        error = ctypes.get_errno()
        if mapped != ctypes.c_void_p(-1).value:
            libc.munmap(mapped, page)
        if error in (errno.EEXIST, errno.EINVAL) or mapped != ctypes.c_void_p(-1).value:
            print(f"SKIP {mode}: MAP_FIXED_NOREPLACE probe unavailable")
            raise SystemExit(77)
        raise OSError(error, "MAP_FIXED_NOREPLACE failed")
    try:
        import recdeep
        native = recdeep.__file__.endswith(".so")
        recdeep.set_limit(2000000 if native else 2000)
        try:
            recdeep.climb()
        except RecursionError as error:
            assert ("native stack" in str(error)) == native, str(error)
        else:
            raise AssertionError("unbounded recursion completed")
        assert recdeep.depth(10) == 10
        print(f"{mode}: RecursionError and recovery")
    finally:
        assert libc.munmap(mapped, page) == 0


if sys.platform != "linux" or platform.libc_ver()[0] != "glibc":
    print("SKIP native stack mappings require Linux/glibc")
    raise SystemExit(77)
elif len(sys.argv) > 1 and sys.argv[1] == "--child":
    probe(sys.argv[2])
else:
    skipped = False
    for mode in ("finite", "none", "unlimited"):
        result = subprocess.run([sys.executable, __file__, "--child", mode], capture_output=True, text=True, timeout=30)
        assert result.returncode in (0, 77) and result.stderr == "", (mode, result.returncode, result.stdout, result.stderr)
        print(result.stdout, end="")
        skipped |= result.returncode == 77
    raise SystemExit(77 if skipped else 0)
