"""Read-only comparisons keep each container's original numeric representation."""


def comparisons() -> None:
    ints = [1, 2]
    floats = [1.0, 2.0]
    print(ints == floats, floats == ints, ints != floats)
    print([1, 2] == [1.0, 2.0], [1.0, 2.0] == [1, 2])
    print([1, 2] != [1.0, 3.0], [1, 2] == [1.0])
    print([True, False] == [1, 0], [1.0, 0.0] == [True, False])
    print((1, 2) == (1.0, 2.0), (True, 2.0) == (1, 2))
    print((1, "x", [2]) == (1.0, "x", [2.0]))
    print({"a": 1} == {"a": 1.0}, {"a": 1.0} != {"b": 1})
    print({(True, "a"): 1} == {(1, "a"): 1.0})
    print([[1, 2]] == [[1.0, 2.0]])
    print({"a": [[1, 2]]} == {"a": [[1.0, 2.0]]})
    print([{"a": (1, [2])}] == [{"a": (1.0, [2.0])}])
    rows = [[1.0, 2.0], [3.0]]
    print(ints in rows, [1, 2] in rows, [3] in rows, [4] not in rows)
    print(ints in [[1.0, 2.0]], [1, 2] in (floats,))
    print((1, 2) in [(1.0, 2.0)], {"a": 1} in [{"a": 1.0}])
    print([{"a": 1}] in [[{"a": 1.0}]], [1] in [[2.0]])
    # Equality does not grant permission to store a float through the int alias.
    alias = ints
    print(alias is ints)
    ints.append(3)
    floats.append(3.0)
    print(ints == floats, ints, floats)
    print(ints == floats == [1, 2, 3])
    # A double cannot distinguish 2**53 + 1 from 2**53; equality must.
    odd = [9007199254740993]
    rounded = [9007199254740992.0]
    print(odd == rounded, rounded == odd, odd != rounded)
    print([9007199254740992.0] == [9007199254740993])
    print((9007199254740993,) == (9007199254740992.0,))
    print({"a": 9007199254740993} == {"a": 9007199254740992.0})
    print(odd in [rounded], odd not in [rounded])
    print([9223372036854775807] == [9223372036854775808.0])
    print([-9223372036854775808] == [-9223372036854775808.0])
    print([0] == [-0.0], [1] == [float("inf")], [1] == [float("nan")])


comparisons()
