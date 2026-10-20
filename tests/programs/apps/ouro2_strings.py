s = "hello"
t = s + ", " + "world"
print(t, len(t), len(""))
print(t[0], t[4], t[-1], t[-5])
print(t[0:5], t[7:], t[:5], t[-5:], t[3:1], t[2:100], t[-100:2])
print(ord("a"), ord(t[1]), ord(t[-1]), chr(65) + chr(66))
print(s == "hello", s != "hello", s == "hellp", s == "hell", "" == "")
print(str(42) + str(-7) + str(0) + str(True) + str("x"))
print("tab\there", "quote\"s", 'single \'q\'', "back\\slash")
print('''triple
quoted''', """with "quotes" inside""")


def rev(s: str) -> str:
    r = ""
    i = len(s) - 1
    while i >= 0:
        r = r + s[i]
        i -= 1
    return r


def count(s: str, c: str) -> int:
    n = 0
    for i in range(len(s)):
        if s[i] == c:
            n += 1
    return n


def is_pal(s: str) -> bool:
    return s == rev(s)


print(rev("stressed"), count("mississippi", "s"), is_pal("racecar"), is_pal("ouro"))
big = ""
for i in range(200):
    big = big + str(i) + ","
print(len(big), big[:20], big[-8:])
print(int("12345") * 2, int("0"), int("-9"))
up = ""
for ch in "abc xyz":
    if ch == " ":
        up = up + "_"
    else:
        up = up + chr(ord(ch) - 32)
print(up)
for ch in "":
    print("never")
