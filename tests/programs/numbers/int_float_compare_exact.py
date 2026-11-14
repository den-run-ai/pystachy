# Comparisons of an int with a float at run time around 2**53: an int of at most that magnitude
# converts to a float exactly, and past it some do not (2**53 + 1 is no float). Each operator in
# both operand orders, against signed zeros, halves, the floats beside 2**53, infinities and NaN.
import sys

n = len(sys.argv)                # 3 (tests/run.sh passes a1 a2): values the compiler cannot fold
two53 = (1 << 50) * (n + 5)      # 2**53
ints = [0, n - 3, 1, -1, n, -n, two53 - 1, two53, two53 + 1, two53 + 2,
        -two53, -two53 + 1, -two53 - 1, -two53 - 2, two53 * 1023 + 1, -two53 * 1023 - 1]
floats = [0.0, -0.0, 0.5, -0.5, 3.0, 3.5, -3.0, 9007199254740991.0, 9007199254740992.0,
          9007199254740994.0, -9007199254740992.0, -9007199254740994.0, 9.223372036854775808e18,
          float("inf"), float("-inf"), float("nan")]


def bits(i: int, f: float) -> str:
    left = [i < f, i <= f, i == f, i != f, i > f, i >= f]
    right = [f < i, f <= i, f == i, f != i, f > i, f >= i]
    return "".join(["1" if b else "0" for b in left + right])


for i in ints:
    print(i, " ".join([bits(i, f) for f in floats]))

# An int loop counter against floats, as a schedule compares them: the steps each float allows.
due = [2.5, 0.0, 7.0, 1e300, float("nan"), -1.0]
taken = [0] * len(due)
for step in range(10 * n):
    for k in range(len(due)):
        if due[k] <= step:
            taken[k] += 1
print(taken)
