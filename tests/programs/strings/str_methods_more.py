def show(parts: list[str]) -> None:
    print(len(parts), parts)


print("a:b:c".partition(":"), "a:b:c".rpartition(":"), "abc".partition(":"), "abc".rpartition(":"))
head, sep, tail = "key = value = x".partition(" = ")
print(head, sep, tail)
print("prefix_name".removeprefix("prefix_"), "name.py".removesuffix(".py"), "x".removeprefix(""), "ab".removesuffix("abc"))
for w in [-1, 0, 3, 4, 5, 6, 7]:
    print(repr("ab".center(w)), repr("abc".center(w, "*")), repr("ab".ljust(w, "-")), repr("ab".rjust(w, ".")))
for z in ["42", "-42", "+7", "", "-", "abc", "€1"]:
    print(repr(z.zfill(5)), repr(z.zfill(1)))
print("é".center(5, "·"), "€".ljust(3, "€"), "ab".rjust(4, "é"))
for t in ["hello world", "HELLO wORLD", "they're bill's", "a1b2 c3", "", "123", "Ab Cd", "Ab cd", "AB"]:
    print(repr(t.title()), repr(t.capitalize()), repr(t.swapcase()), t.istitle(), repr(t.casefold()))
for a in ["abc", "", "ab\x7f", "é", "123", "1.5"]:
    print(a.isascii(), a.isdecimal(), a.isnumeric())
for lines in ["a\nb\r\nc\rd", "", "\n", "a\n\nb\n", "x\x0by\x0cz\x1cw\x1dv\x1eu", "p q r\x85s", "no break"]:
    print(lines.splitlines(), lines.splitlines(True))
print(repr("a\tb\tc".expandtabs()), repr("ab\tc\n\td".expandtabs(4)), repr("x\ty".expandtabs(0)), repr("é\tx".expandtabs(4)), repr("12345678\tx".expandtabs()))
show("a,b,,c".rsplit(","))
show("a,b,,c".rsplit(",", 1))
show("a,b,,c".rsplit(",", 0))
show("  a b  c  ".rsplit())
show("  a b  c  ".rsplit(None, 1))
show("  a b  c  ".rsplit(None, 0))
show("  a b  c  ".split(None, 1))
show("  a b  c  ".split(None, 0))
show("   ".rsplit())
show("".rsplit(","))
show("aaa".rsplit("aa"))
show("aaa".split("aa"))
print(" x ".strip(None), "x--".rstrip(None))
print("ab".center(5, "xy"))
