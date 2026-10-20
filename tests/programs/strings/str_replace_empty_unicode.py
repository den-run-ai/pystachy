# replace("", new) puts new between code points, as CPython does, and not between the bytes of
# their UTF-8: "é".replace("", "x") was "x\xc3x\xa9x", malformed text, and is "xéx". A count
# stops after that many characters, and then the rest is copied whole. bytes.replace() still puts
# new between bytes. The text also comes from stdin, so that no literal is folded.
print(repr("é".replace("", "x")), len("é".replace("", "x")))
print(repr("aé日😀".replace("", "-")), repr("ab".replace("", "é")), repr("aé".replace("", "")))
print(repr("".replace("", "€")), repr("".replace("", "€", 0)), repr("".replace("", "€", 3)))
print(repr("e\u0301".replace("", "|")), repr(chr(0xD800).replace("", "-")))
for n in [-9223372036854775807 - 1, -1, 0, 1, 2, 3, 4, 5, 6, 2**62]:
    print(n, repr("aé日😀".replace("", "·", n)), repr("日本".replace("", "", n)))

line = input()
r = line.replace("", "/")
print(repr(r), len(r), r[1], r[-2], list(r)[:6], r.count("/"), r.find("é"))
print(repr(line.replace("", "<>", 4)), repr(line.replace("", "", 2)) == repr(line))
print("".join([c + "/" for c in line]) == r[1:], r.split("/")[1:-1] == list(line))
print(repr(b"\xc3\xa9".replace(b"", b"-")), repr(b"ab".replace(b"", b"\xc3\xa9", 2)))
print(repr(line.encode().replace(b"", b"/", 3)))
