"""One str method on a long text: opbench.py METHOD REPS COPIES TEXT.

The text is TEXT, COPIES times. The result of each call is only tested, so that the count of
its characters is not part of what a run measures."""
import sys


def run(text: str, reps: int, op: str) -> int:
    total = 0
    for _ in range(reps):
        if op == "lower":
            total += 1 if text.lower() else 0
        elif op == "upper":
            total += 1 if text.upper() else 0
        elif op == "swapcase":
            total += 1 if text.swapcase() else 0
        elif op == "casefold":
            total += 1 if text.casefold() else 0
        elif op == "title":
            total += 1 if text.title() else 0
        elif op == "capitalize":
            total += 1 if text.capitalize() else 0
        elif op == "isupper":
            total += int(text.isupper())
        elif op == "islower":
            total += int(text.islower())
        elif op == "istitle":
            total += int(text.istitle())
        elif op == "isalpha":
            total += int(text.isalpha())
        elif op == "isalnum":
            total += int(text.isalnum())
        elif op == "isdecimal":
            total += int(text.isdecimal())
        elif op == "isdigit":
            total += int(text.isdigit())
        elif op == "isnumeric":
            total += int(text.isnumeric())
        elif op == "isspace":
            total += int(text.isspace())
        elif op == "repr":
            total += 1 if repr(text) else 0
        else:
            raise ValueError(op)
    return total


op = sys.argv[1]
reps = int(sys.argv[2])
n = int(sys.argv[3])
print(run(sys.argv[4] * n, reps, op))
