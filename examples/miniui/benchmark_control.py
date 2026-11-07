"""Benchmark-only controls, common ABI for real and counting raylib adapters."""
from ffi import extern, c_int, c_int64


@extern("libminiui.so", "miniui_bench_configure")
def configure() -> None: ...


@extern("libminiui.so", "miniui_bench_reset")
def reset() -> None: ...


@extern("libminiui.so", "miniui_bench_calls")
def calls() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_hash")
def digest() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_rects")
def rects() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_texts")
def texts() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_clips")
def clips() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_begins")
def begins() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_ends")
def ends() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_widths")
def widths() -> c_int64: ...


@extern("libminiui.so", "miniui_bench_snapshot")
def snapshot(path: str) -> c_int: ...
