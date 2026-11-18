# An object whose class defines __getitem__ is a mapping to %, but a format whose only "%(" is
# escaped ("%%(") and whose conversion is positional formats the object itself.
class Table:
    def __getitem__(self, k: str) -> str:
        return k

    def __str__(self) -> str:
        return "Table"


print("50%%(est.) of %s" % Table())
d = {"a": 1}
print("100%%(all) %s" % (d,))
