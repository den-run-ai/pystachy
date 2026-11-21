"""WASI wrappers for libc calls whose Pystachy ABI uses 64-bit lengths."""

LIBC_WRAPPERS: dict[str, str] = {
    "memcmp": "pys_wasi_memcmp",
    "memchr": "pys_wasi_memchr",
    "memmem": "pys_wasi_memmem",
}
