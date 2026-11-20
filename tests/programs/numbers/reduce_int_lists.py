# any() and all() of a list of ints or bools, and sum() of ints from a float start, which adds
# each int as a float in the list's order, without the compensation that a sum of floats has.
def show(xs: list[int]) -> None:
    print(xs, any(xs), all(xs), repr(sum(xs, 0.5)), repr(sum(xs, -0.0)))


cases: list[list[int]] = [[], [0], [1], [-1], [0, 0, 0], [0, 0, 7], [7, 0, 0], [3, 2, 1], [1, 2, 0], [-9223372036854775808],
                          [9223372036854775807, 1, -9223372036854775807], [0] * 100 + [5], [5] * 100 + [0]]
for xs in cases:
    show(xs)

flags: list[bool] = [True, False, True]
print(any(flags), all(flags), sum(flags, 0.25), any([False, False]), all([True, True]), all(flags[:1]), any(flags[1:2]))
none: list[bool] = []
print(any(none), all(none), sum(none, 1.5))
big = [9007199254740992, 1, 1, 1]
print(repr(sum(big, 0.0)), repr(sum(big[1:] + big[:1], 0.0)), repr(sum(big, float("inf"))), repr(sum(big, float("nan"))))
print(repr(sum([0], -0.0)), repr(sum([4611686018427387904, 4611686018427387904, 4611686018427387904], 1e300)), repr(sum([-1, 1], 1e-300)))
