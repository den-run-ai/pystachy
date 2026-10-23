# Disjoint scalar elements compare equal only when both sets are empty.
for filled in [False, True]:
    ints: set[int] = set()
    words: set[str] = set()
    data: set[bytes] = set()
    if filled:
        # All three keys hash to zero; comparison must not decode another layout.
        ints.add(0)
        words.add("")
        data.add(b"")
    fi: frozenset[int] = frozenset(ints)
    fw: frozenset[str] = frozenset(words)
    fd: frozenset[bytes] = frozenset(data)
    print("sets", filled,
          ints == words, words == ints, ints != words, words != ints,
          ints == data, data == ints, ints != data, data != ints,
          words == data, data == words, words != data, data != words)
    print("frozen", filled,
          fi == fw, fw == fi, fi != fw, fw != fi,
          fi == fd, fd == fi, fi != fd, fd != fi,
          fw == fd, fd == fw, fw != fd, fd != fw)
    print("mixed int/str", filled,
          ints == fw, fw == ints, ints != fw, fw != ints,
          fi == words, words == fi, fi != words, words != fi)
    print("mixed int/bytes", filled,
          ints == fd, fd == ints, ints != fd, fd != ints,
          fi == data, data == fi, fi != data, data != fi)
    print("mixed str/bytes", filled,
          words == fd, fd == words, words != fd, fd != words,
          fw == data, data == fw, fw != data, data != fw)
    print("compatible", ints == fi, fi == ints, words == fw, data == fd, ints != fi)

ints.clear()
print("one empty", ints == words, words == ints, ints != data, data != ints)
print("numeric control", {1} == {int(True)}, True in {1})
print("tuple control", {(1, 2)} == {(1, 2)})

changing: set[int] = set()


def mutate_left() -> set[str]:
    print("right operand ran")
    changing.add(0)
    empty: set[str] = set()
    return empty


# Read lengths after evaluating the RHS, which changes the already evaluated LHS.
print("right mutation", changing == mutate_left(), len(changing))
