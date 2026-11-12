# list.extend() of a str (its characters), a tuple, a dict (its keys), a set and a bytes.
def main() -> None:
    acc: list[str] = []
    acc.extend("héllo")
    acc.extend("")
    acc.extend(("a", "b"))
    acc.extend({"k": 1, "j": 2})
    acc.extend({"only"})
    acc.extend(tuple(["t", "u"]))
    print(acc, "".join(acc))
    nums: list[int] = [0]
    nums.extend(b"\x01\x02")
    nums.extend((3, 4))
    nums.extend({5: "x"})
    nums.extend(range(6, 8))
    print(nums)
    opt: list[str | None] = [None]
    opt.extend("ab")
    print(opt)
    acc.pop()
    acc.extend(acc[:2])
    print(len(acc), acc[-1])


main()
