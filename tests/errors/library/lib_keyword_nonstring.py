# error: expected str | None, got int
# This port's compiled predicates accept strings and None, not other key types.
import keyword
print(keyword.iskeyword(1))
