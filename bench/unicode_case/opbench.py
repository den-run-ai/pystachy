"""One str case method on a long text: opbench.py METHOD REPS COPIES TEXT.

The text is TEXT and a space, COPIES times. The result of each call is only tested, so that
the count of its characters is not part of what a run measures."""
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
        else:
            total += int(text.istitle())
    return total


op = sys.argv[1]
reps = int(sys.argv[2])
n = int(sys.argv[3])
base = sys.argv[4]
print(run((base + " ") * n, reps, op))
