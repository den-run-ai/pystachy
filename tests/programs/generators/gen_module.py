# Generators of an imported module (#490): an __iter__ that yields, iterated by for, in and
# list(); a template generator; generators the program never calls compile only where called.
from mods.genmod import Lines, chunks

ls = Lines("a\nb\nc")
print(ls.count())
print("a" in ls, "z" in ls)
for line in ls:
    print("line", line)
print(list(ls), sorted(ls, reverse=True))
for c in chunks([1, 2, 3, 4, 5], 2):
    print(c)
print(list(chunks("abcde", 3)))
