# error: cannot compare int | None == str | None
x: int | None = None
s: str | None = None
print(x == s)  # (True in CPython: both are None)
