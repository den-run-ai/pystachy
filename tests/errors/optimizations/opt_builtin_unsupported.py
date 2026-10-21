# error: unsupported call id(str | None)
def get() -> str | None:
    return None


print(id(get()) == id(None))  # (id() is not supported for a str either)
