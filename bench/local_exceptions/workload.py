"""Caught lookup failures: run CASE REPEATS; print checksum and elapsed seconds."""
import sys
from time import perf_counter


def dict_read(keys: list[int], repeats: int) -> int:
    cache = {i: i * 3 for i in range(256)}
    total = 0
    for _ in range(repeats):
        for key in keys:
            try:
                total += cache[key]
            except KeyError:
                total += 1
    return total


def list_read(keys: list[int], repeats: int) -> int:
    values = [i * 3 for i in range(256)]
    total = 0
    for _ in range(repeats):
        for key in keys:
            try:
                total += values[key]
            except IndexError:
                total += 1
    return total


def word_count(words: list[str], repeats: int) -> int:
    total = 0
    for _ in range(repeats):
        counts: dict[str, int] = {}
        for word in words:
            try:
                counts[word] += 1
            except KeyError:
                counts[word] = 1
        total += sum(counts.values()) + len(counts)
    return total


def index_miss(keys: list[int], repeats: int) -> int:
    values = list(range(16))
    total = 0
    for _ in range(repeats):
        for key in keys:
            try:
                total += values.index(key)
            except ValueError:
                total += 1
    return total


def int_miss(words: list[str], repeats: int) -> int:
    total = 0
    for _ in range(repeats):
        for word in words:
            try:
                total += int(word)
            except ValueError:
                total += 1
    return total


case = sys.argv[1]
repeats = int(sys.argv[2])
keys = [i % 256 if case.endswith("hit") else i for i in range(512)]
if case.endswith("miss"):
    keys = [i + 256 for i in range(512)]
words = [str(i % 256) for i in range(512)]
if case == "int_miss":
    words = ["bad" + str(i) for i in range(512)]
started = perf_counter()
if case.startswith("dict_"):
    checksum = dict_read(keys, repeats)
elif case.startswith("list_"):
    checksum = list_read(keys, repeats)
elif case == "word_count":
    checksum = word_count(words, repeats)
elif case == "index_miss":
    checksum = index_miss(keys, repeats)
elif case == "int_miss":
    checksum = int_miss(words, repeats)
else:
    raise ValueError("unknown benchmark case")
elapsed = perf_counter() - started
print(checksum)
print(elapsed)
