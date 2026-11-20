#!/usr/bin/env python
"""
Pure-Python Implementation of the AES block-cipher.

Benchmark AES in CTR mode using the pyaes module.
"""

import time  # Pystachy port: time.perf_counter() is pyperf.perf_counter(); pyperf is not imported

import pyaes

TIMED: list[float] = []  # Pystachy port: the seconds of each timed part

# 23,000 bytes
CLEARTEXT = b"This is a test. What could possibly go wrong? " * 500

# 128-bit key (16 bytes)
KEY = b'\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,'


def bench_pyaes(loops):
    range_it = range(loops)
    t0 = time.perf_counter()  # Pystachy port: time.perf_counter() is pyperf.perf_counter()

    for loops in range_it:
        aes = pyaes.AESModeOfOperationCTR(KEY)
        ciphertext = aes.encrypt(CLEARTEXT)

        # need to reset IV for decryption
        aes = pyaes.AESModeOfOperationCTR(KEY)
        plaintext = aes.decrypt(ciphertext)

        # explicitly destroy the pyaes object
        aes = None

    TIMED.append(time.perf_counter() - t0)  # Pystachy port: the seconds, which upstream returns
    if plaintext != CLEARTEXT:
        raise Exception("decrypt error!")

    return ciphertext  # Pystachy port: the last loop's ciphertext, for the check


if __name__ == "__main__":
    # Pystachy port: a deterministic main replaces pyperf.Runner: argv[1] is the
    # number of loops; the ciphertext's length and digest are printed, and the time
    # goes to stderr.
    import hashlib
    import sys
    loops = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    ciphertext = bench_pyaes(loops)
    print("seconds", sum(TIMED), file=sys.stderr)
    print("crypto_pyaes", loops, len(ciphertext), hashlib.md5(ciphertext).hexdigest(), ciphertext[:16])
