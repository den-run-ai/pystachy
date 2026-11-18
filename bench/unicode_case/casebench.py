"""The str case methods together: casebench.py long|short REPS TEXT.

long calls all nine on TEXT and a space, 2000 times; short calls lower, upper, islower and
title on each word of TEXT."""
import sys


def long_ops(text: str, reps: int) -> int:
    total = 0
    for _ in range(reps):
        total += len(text.lower()) + len(text.upper()) + len(text.swapcase()) + len(text.casefold())
        total += len(text.title()) + len(text.capitalize())
        total += int(text.isupper()) + int(text.islower()) + int(text.istitle())
    return total


def short_ops(words: list[str], reps: int) -> int:
    total = 0
    for _ in range(reps):
        for w in words:
            total += len(w.lower()) + len(w.upper()) + int(w.islower()) + len(w.title())
    return total


mode = sys.argv[1]
reps = int(sys.argv[2])
base = sys.argv[3]
if mode == "long":
    print(long_ops((base + " ") * 2000, reps))
else:
    print(short_ops(base.split(), reps))
