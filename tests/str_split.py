print("a,b,c".split(",", 1), "a b  c d".split(), "  a b  c  ".split(" "), "a,b".split(",", 0), "x".split(",", 5))
k, v = "key = value = more".split("=", 1)
print(repr(k.strip()), repr(v.strip()), "a,b,c".split(",", -1), "a::b::c".split("::", 1))
s = "  one two   three  "
print(s.split(), " ".join(s.split()))
