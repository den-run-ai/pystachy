# error: unsupported call hash(str | None)
def get() -> str | None:
    return None


print(hash(get()) == hash(None))  # (hash() is not supported for a str either)
