# str.replace(old, new, count): the first count occurrences, left to right without overlaps; a
# negative count replaces all and 0 none. An empty old inserts new before each of the first
# count characters (and at the end once count reaches it). count may be a bool, and given by
# name (Python 3.13). The method also works as a bound or unbound method value.
s = "a-b-c-d"
for n in [-5, -1, 0, 1, 2, 3, 4, 100]:
    print(n, s.replace("-", "+", n), s.replace("-", "", n), s.replace("-", "<->", n))
print("aaaa".replace("aa", "b", 1), "aaaa".replace("aa", "b", 2), "aaaaa".replace("aa", "b", 5))
print("aaa".replace("a", "b", 1), "aaa".replace("a", "b", True), "aaa".replace("a", "b", False))
print("aaa".replace("x", "b", 2), "".replace("a", "b", 3), repr("".replace("", "b", 0)))
for n in [-1, 0, 1, 2, 3, 4, 9]:
    print(n, "abc".replace("", "-", n), repr("".replace("", "-", n)), "abc".replace("", "", n))
print(s.replace("-", "=", count=2), s.replace("b", "B", count=0))
k = 2
print(s.replace("-", "/", k), s.replace("-", "/", k - 3), s.replace("-", "/", k * k))

# non-ASCII text: whole characters are found and replaced
t = "été à Paris, été à Lyon, été"
print(t.replace("été", "summer", 2), t.replace("à", "in", 1), t.replace("é", "e", 3))
print("日本語日本語".replace("本", "x", 1), "naïve".replace("ï", "i", -1))

# as a value
rep = "aaa".replace
print(rep("a", "b", 1), rep("a", "b"), rep("a", "b", count=2))
print(str.replace("aaa", "a", "b", 1), str.replace("abab", "b", "", 1))


# arguments are evaluated in order, before the replacement
def arg(tag: str, v: int) -> int:
    print("arg", tag)
    return v


def text(tag: str, v: str) -> str:
    print("arg", tag)
    return v


print(text("s", "xyxyx").replace(text("old", "x"), text("new", "z"), arg("count", 2)))


class Doc:
    def __init__(self, body: str) -> None:
        self.body = body

    def redact(self, word: str, times: int) -> str:
        return self.body.replace(word, "*" * len(word), times)


print(Doc("one two one two one").redact("one", 2))
print(Doc("one two one two one").redact("two", -1))
