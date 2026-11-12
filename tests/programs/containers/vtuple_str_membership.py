# x in t and t.count(x) of a runtime-length tuple of strs: equal strs that are different
# objects, the empty str, non-ASCII text, a prefix of an item, None among the items, and
# the empty tuple.
import sys

OPENERS = tuple({"[": "]", "{": "}", "(": ")"})


def joined(parts: list[str]) -> str:
    return "".join(parts)


def main() -> None:
    made = joined(["[", ""])  # (not the constant's object)
    print(made in OPENERS, "{" in OPENERS, ")" in OPENERS, "" in OPENERS, "[{" in OPENERS, "[" not in OPENERS)
    words = tuple(sys.argv[1:] + ["alpha", "beta", "alpha", "", "é", "日本"])
    for w in ["alpha", joined(["al", "pha"]), "alph", "alphaa", "", "é", "e", "日本", "日", "gamma"]:
        print(repr(w), w in words, w not in words, words.count(w))
    opt: tuple[str | None, ...] = tuple([None, "a", None, joined(["a"])])
    print(None in opt, "a" in opt, "b" in opt, opt.count(None), opt.count("a"), opt.count("b"))
    empty: tuple[str, ...] = tuple([w for w in words if w == "none"])
    print("x" in empty, "" in empty, empty.count(""), len(empty))
    hits = 0
    for ch in "a[b{c(d)e]f}":
        if ch in OPENERS:
            hits += 1
    print(hits)


main()
