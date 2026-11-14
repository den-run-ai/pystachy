# float ** float, pow() and math.pow() on both sides of libm's case (a positive base and a finite
# result) and through each error, with operands read at run time so that none folds while the
# program compiles. Loops go on after the errors they catch, and change lists in their handlers.
import math


def power(b: float, e: float) -> str:
    try:
        return repr(b ** e)
    except (ZeroDivisionError, ValueError, OverflowError) as err:
        return type(err).__name__ + ": " + str(err)


def builtin(b: float, e: float) -> str:
    try:
        return repr(pow(b, e))
    except (ZeroDivisionError, ValueError, OverflowError) as err:
        return type(err).__name__ + ": " + str(err)


def mathpow(b: float, e: float) -> str:
    try:
        return repr(math.pow(b, e))
    except (ValueError, OverflowError) as err:
        return type(err).__name__ + ": " + str(err)


n = int(input())
bases: list[float] = []
exps: list[float] = []
for _ in range(n):
    words = input().split()
    bases.append(float(words[0]))
    exps.append(float(words[1]))

for i in range(n):
    b = bases[i]
    e = exps[i]
    print(repr(b), repr(e), "|", power(b, e), "|", builtin(b, e), "|", mathpow(b, e))
# (b ** e is complex there in CPython: tests/deviations/complex_pow.py)
print("negative base, fractional exponent:", mathpow(bases[7], exps[0]))

# A loop that catches each error, appends to the list it reads in the handler, and goes on.
kept: list[float] = [1.0]
for i in range(n):
    try:
        kept[len(kept) - 1] += bases[i] ** exps[i]
    except (ZeroDivisionError, ValueError, OverflowError):
        kept.append(float(i))
print(len(kept), kept)

# The same base and exponent at every step, the stores between them, and an error that stops a loop
# after it has stored some results.
c = bases[0]
d = exps[0]
acc: list[float] = [0.0, 0.0, 0.0]
for j in range(30):
    acc[j % 3] += c ** d + math.pow(c, d)
print(acc)
out: list[float] = []
k = 0
try:
    for k in range(n):
        out.append(bases[k] ** exps[k])
except (ZeroDivisionError, ValueError, OverflowError) as err:
    print("stopped at", k, "after", len(out), type(err).__name__)
print(out)
