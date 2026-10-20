# range(), reversed(), enumerate() and zip() where their items are used at once, x in range(...),
# and any()/all() over items of any type.
xs = [3, 1, 2]
s = "héllo"
d = {"a": 1, "b": 2}
print(list(reversed(xs)), "".join(reversed("abc")), list(reversed(d)), sorted(reversed(xs)))
print(list(enumerate(xs)), list(enumerate("ab", 1)), list(zip(xs, "abc")), list(zip(xs)))
print(sum(range(10)), max(range(3, 9, 2)), list(range(5, 0, -2)), sorted(range(3), reverse=True))
print(any(reversed([0, 0, 1])), all(zip(xs, xs)), min(enumerate(xs)))
print(3 in range(10), 10 in range(10), -1 in range(10), 4 in range(0, 10, 2), 5 in range(0, 10, 2), 5 not in range(10, 0, -5))
print(7 in range(10, 0, -3), -9223372036854775808 in range(-9223372036854775807 - 1, 9223372036854775807, 3))
print(",".join([str(i) for i in reversed(range(4))]), list(reversed(list(range(3)))))
print(any(["", "x"]), all(["a", ""]), any([0.0, 0.0]), all([[1], [2]]), any([[1], []]), any([[0][:0]]))
