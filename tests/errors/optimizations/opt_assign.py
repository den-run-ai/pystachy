# error: the value pick() returns (str) may be None (str | None); test it with 'is not None' first
# The new local binding may carry None; the explicit return type remains a contract.
def pick(x: str | None) -> str:
    y = "default"
    y = x
    return y


print(pick("a"))
