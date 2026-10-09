# error: cannot compare dict[str,int] | None < dict[str,int]
def get() -> dict[str, int] | None:
    return None


print(get() < {"a": 1})
