# error: zip() is only supported in a for loop
# zip(), enumerate(), map() and filter() are not values in Pystachy (lib/compatibility.md): a
# generator expression over them is one
from itertools import islice

print(list(islice(zip("abc", [1, 2, 3]), 2)))
