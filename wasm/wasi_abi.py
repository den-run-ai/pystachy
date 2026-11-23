"""WASI wrappers for libc calls whose Pystachy ABI uses 64-bit lengths, and for musl's fma."""

LIBC_WRAPPERS: dict[str, str] = {
    "memcmp": "pys_wasi_memcmp",
    "memchr": "pys_wasi_memchr",
    "memmem": "pys_wasi_memmem",
    "llvm.fma.f64": "pys_wasi_fma",
}
