"""Benchmark for the base64 module's primary public APIs.

Tests encoding and decoding performance across various variants
and data sizes, split into _small (balanced small data) and _large variants.

Small weighs towards measuring overhead, large measures the core algorithm
loop implementation.
"""

import base64
import random
import time

# Pystachy port: pyperf is not imported; the main below replaces pyperf.Runner.
TIMED: list[float] = []  # Pystachy port: the seconds of each timed part


# Pystachy port: random.randbytes() takes one getrandbits() of all its bits, beyond the
# 63 that Pystachy's has; these bytes come from randrange(), so the data differ from
# upstream's.
def randbytes(n):
    return bytes([random.randrange(256) for _ in range(n)])


# Generate test data with a fixed seed for reproducibility
random.seed(12345)
# Pystachy port: the randbytes() above, for random.randbytes()
DATA_TINY = randbytes(20)
DATA_SMALL = randbytes(127)  # odd on purpose
DATA_MEDIUM = randbytes(3072)
DATA_9K = randbytes(9000)
DATA_LARGE = randbytes(102400)
DATA_HUGE = randbytes(1048574)  # 1M-2

# Pre-encoded data for decode benchmarks
B64_TINY = base64.b64encode(DATA_TINY)
B64_SMALL = base64.b64encode(DATA_SMALL)
B64_MEDIUM = base64.b64encode(DATA_MEDIUM)
B64_9K_STR = base64.b64encode(DATA_9K).decode('ascii')
B64_LARGE = base64.b64encode(DATA_LARGE)
B64_HUGE = base64.b64encode(DATA_HUGE)

B64_URLSAFE_TINY = base64.urlsafe_b64encode(DATA_TINY)
B64_URLSAFE_SMALL = base64.urlsafe_b64encode(DATA_SMALL)
B64_URLSAFE_MEDIUM = base64.urlsafe_b64encode(DATA_MEDIUM)
B64_URLSAFE_9K_STR = base64.urlsafe_b64encode(DATA_9K).decode('ascii')

B32_TINY = base64.b32encode(DATA_TINY)
B32_SMALL = base64.b32encode(DATA_SMALL)
B32_MEDIUM = base64.b32encode(DATA_MEDIUM)
B32_9K_STR = base64.b32encode(DATA_9K).decode('ascii')
B32_LARGE = base64.b32encode(DATA_LARGE)
B32_HUGE = base64.b32encode(DATA_HUGE)

B16_TINY = base64.b16encode(DATA_TINY)
B16_SMALL = base64.b16encode(DATA_SMALL)
B16_MEDIUM = base64.b16encode(DATA_MEDIUM)
B16_9K_STR = base64.b16encode(DATA_9K).decode('ascii')
B16_LARGE = base64.b16encode(DATA_LARGE)
B16_HUGE = base64.b16encode(DATA_HUGE)

A85_TINY = base64.a85encode(DATA_TINY)
A85_SMALL = base64.a85encode(DATA_SMALL)
A85_MEDIUM = base64.a85encode(DATA_MEDIUM)
A85_9K_STR = base64.a85encode(DATA_9K).decode('ascii')
A85_LARGE = base64.a85encode(DATA_LARGE)
A85_HUGE = base64.a85encode(DATA_HUGE)

B85_TINY = base64.b85encode(DATA_TINY)
B85_SMALL = base64.b85encode(DATA_SMALL)
B85_MEDIUM = base64.b85encode(DATA_MEDIUM)
B85_9K_STR = base64.b85encode(DATA_9K).decode('ascii')
B85_LARGE = base64.b85encode(DATA_LARGE)
B85_HUGE = base64.b85encode(DATA_HUGE)


# --- Base64 ---

def bench_b64_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.b64encode(DATA_TINY)
            base64.b64decode(B64_TINY)
        for _ in range(71):
            base64.b64encode(DATA_SMALL)
            base64.b64decode(B64_SMALL)
        for _ in range(3):
            base64.b64encode(DATA_MEDIUM)
            base64.b64decode(B64_MEDIUM)
        base64.b64encode(DATA_9K)
        base64.b64decode(B64_9K_STR)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


def bench_b64_large(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(10):
            base64.b64encode(DATA_LARGE)
            base64.b64decode(B64_LARGE)
        base64.b64encode(DATA_HUGE)
        base64.b64decode(B64_HUGE)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


# --- URL-safe Base64 (small only) ---

def bench_urlsafe_b64_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.urlsafe_b64encode(DATA_TINY)
            base64.urlsafe_b64decode(B64_URLSAFE_TINY)
        for _ in range(71):
            base64.urlsafe_b64encode(DATA_SMALL)
            base64.urlsafe_b64decode(B64_URLSAFE_SMALL)
        for _ in range(3):
            base64.urlsafe_b64encode(DATA_MEDIUM)
            base64.urlsafe_b64decode(B64_URLSAFE_MEDIUM)
        base64.urlsafe_b64encode(DATA_9K)
        base64.urlsafe_b64decode(B64_URLSAFE_9K_STR)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


# --- Base32 ---

def bench_b32_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.b32encode(DATA_TINY)
            base64.b32decode(B32_TINY)
        for _ in range(71):
            base64.b32encode(DATA_SMALL)
            base64.b32decode(B32_SMALL)
        for _ in range(3):
            base64.b32encode(DATA_MEDIUM)
            base64.b32decode(B32_MEDIUM)
        base64.b32encode(DATA_9K)
        base64.b32decode(B32_9K_STR)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


def bench_b32_large(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(10):
            base64.b32encode(DATA_LARGE)
            base64.b32decode(B32_LARGE)
        base64.b32encode(DATA_HUGE)
        base64.b32decode(B32_HUGE)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


# --- Base16 ---

def bench_b16_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.b16encode(DATA_TINY)
            base64.b16decode(B16_TINY)
        for _ in range(71):
            base64.b16encode(DATA_SMALL)
            base64.b16decode(B16_SMALL)
        for _ in range(3):
            base64.b16encode(DATA_MEDIUM)
            base64.b16decode(B16_MEDIUM)
        base64.b16encode(DATA_9K)
        base64.b16decode(B16_9K_STR)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


def bench_b16_large(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(10):
            base64.b16encode(DATA_LARGE)
            base64.b16decode(B16_LARGE)
        base64.b16encode(DATA_HUGE)
        base64.b16decode(B16_HUGE)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


# --- Ascii85 (includes wrapcol=76) ---

def bench_a85_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.a85encode(DATA_TINY)
            base64.a85encode(DATA_TINY, wrapcol=76)
            base64.a85decode(A85_TINY)
            base64.a85decode(A85_TINY)  # balance enc+dec weight
        for _ in range(71):
            base64.a85encode(DATA_SMALL)
            base64.a85encode(DATA_SMALL, wrapcol=76)
            base64.a85decode(A85_SMALL)
            base64.a85decode(A85_SMALL)  # balance enc+dec weight
        for _ in range(3):
            base64.a85encode(DATA_MEDIUM)
            base64.a85encode(DATA_MEDIUM, wrapcol=76)
            base64.a85decode(A85_MEDIUM)
            base64.a85decode(A85_MEDIUM)  # balance enc+dec weight
        base64.a85encode(DATA_9K)
        base64.a85encode(DATA_9K, wrapcol=76)
        base64.a85decode(A85_9K_STR)
        base64.a85decode(A85_9K_STR)  # balance enc+dec weight
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


def bench_a85_large(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(10):
            base64.a85encode(DATA_LARGE)
            base64.a85encode(DATA_LARGE, wrapcol=76)
            base64.a85decode(A85_LARGE)
            base64.a85decode(A85_LARGE)  # balance enc+dec weight
        base64.a85encode(DATA_HUGE)
        base64.a85encode(DATA_HUGE, wrapcol=76)
        base64.a85decode(A85_HUGE)
        base64.a85decode(A85_HUGE)  # balance enc+dec weight
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


# --- Base85 ---

def bench_b85_small(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(450):
            base64.b85encode(DATA_TINY)
            base64.b85decode(B85_TINY)
        for _ in range(71):
            base64.b85encode(DATA_SMALL)
            base64.b85decode(B85_SMALL)
        for _ in range(3):
            base64.b85encode(DATA_MEDIUM)
            base64.b85decode(B85_MEDIUM)
        base64.b85encode(DATA_9K)
        base64.b85decode(B85_9K_STR)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


def bench_b85_large(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()
    for _ in range_it:
        for _ in range(10):
            base64.b85encode(DATA_LARGE)
            base64.b85decode(B85_LARGE)
        base64.b85encode(DATA_HUGE)
        base64.b85decode(B85_HUGE)
    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops. Upstream's eleven benchmarks run in its order; digests of every
    # encoding and the decoded round trips are printed outside the timers, and the time
    # goes to stderr.
    import hashlib
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    bench_b64_small(loops)
    bench_b64_large(loops)
    bench_urlsafe_b64_small(loops)
    bench_b32_small(loops)
    bench_b32_large(loops)
    bench_b16_small(loops)
    bench_b16_large(loops)
    bench_a85_small(loops)
    bench_a85_large(loops)
    bench_b85_small(loops)
    bench_b85_large(loops)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("base64", loops, len(TIMED))
    for data in [DATA_TINY, DATA_SMALL, DATA_MEDIUM, DATA_9K, DATA_LARGE, DATA_HUGE]:
        b64 = base64.b64encode(data)
        url = base64.urlsafe_b64encode(data)
        b32 = base64.b32encode(data)
        b16 = base64.b16encode(data)
        a85 = base64.a85encode(data)
        wrapped = base64.a85encode(data, wrapcol=76)
        b85 = base64.b85encode(data)
        assert base64.b64decode(b64) == data and base64.urlsafe_b64decode(url) == data
        assert base64.b32decode(b32) == data and base64.b16decode(b16) == data
        assert base64.a85decode(a85) == data and base64.a85decode(wrapped) == data
        assert base64.b85decode(b85) == data
        assert base64.b64decode(b64.decode('ascii')) == data and base64.b85decode(b85.decode('ascii')) == data
        print(len(data), hashlib.md5(data).hexdigest(), hashlib.md5(b64).hexdigest(), hashlib.md5(url).hexdigest(),
              hashlib.md5(b32).hexdigest(), hashlib.md5(b16).hexdigest(), hashlib.md5(a85).hexdigest(),
              hashlib.md5(wrapped).hexdigest(), hashlib.md5(b85).hexdigest())
