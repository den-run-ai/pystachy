"""Unannotated scalar functions for the native dynamic execution prototype.

This source is parsed as data by tools/native_dynamic.py. It is never imported by
CPython during native execution. The interpreter and specialization compiler run
as native Pystachy programs; see tools/native_dynamic_check.py for the experiment.
"""


def helper(x):
    return x * x


def sumsq(n):
    total = 0
    i = 0
    while i < n:
        total = total + helper(i)
        i = i + 1
    return total


def weighted_sum(x, n):
    total = x
    i = 0
    while i < n:
        total = total + helper(x)
        i = i + 1
    return total


def batch(n, count):
    total = 0
    i = 0
    while i < count:
        total = total + sumsq(n + i % 7)
        i = i + 1
    return total


def add(x, y):
    return x + y


def echo(x):
    return x


def mixed_local(n):
    local = n
    if n > 0:
        local = "warm"
    return local


def divide(x, y):
    return x // y


def float_floor(x):
    if x > 0.0:
        return 1.0
    return x // 2.0


def float_remainder(x):
    if x > 0.0:
        return 1.0
    return x % 2.0


def annotated(x: int) -> int:
    return x


def optional(x):
    if x > 0:
        return x
