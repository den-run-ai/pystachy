# error: round() with an ndigits that may be None (int | None) is not supported: it returns an int where ndigits is None, else a float
n: int | None = None
print(round(2.5, n))
