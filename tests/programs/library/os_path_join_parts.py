import os

# os.path.join of two parts and of more: an absolute part starts over, an empty first part adds
# no separator, and a part that ends with "/" gets none.
for a, b in [("", ""), ("", "b"), ("a", ""), ("a", "b"), ("a/", "b"), ("a//", "b"), ("a", "/b"), ("/", "b"), ("/", ""), ("a", "//b"),
             ("é", "€"), ("a b", "c d"), ("a/", "/"), ("a", "b/"), (".", ".."), ("~", "x"), ("a\x00", "b"), ("𝄞/", "𝄞")]:
    print(repr(os.path.join(a, b)))
print(repr(os.path.join("a", "b", "c")), repr(os.path.join("a", "", "c")), repr(os.path.join("a", "/b", "c")), repr(os.path.join("", "", "")))
print(repr(os.path.join("a", "b", "")), repr(os.path.join("", "a", "", "")), repr(os.path.join("a")), repr(os.path.join("/")))
long = os.path.join("x" * 300, "y" * 300)
print(len(long), long[298:303], os.path.join(long, "/z"), len(os.path.join(long, long)))
