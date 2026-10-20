# error: closed union operations require narrowing with isinstance() first
# Only unions of numbers order without narrowing: CPython raises TypeError where a str and an int
# meet, which an int | str list's items may.
xs: list[int | str] = [1, "a"]
print(sorted(xs))
