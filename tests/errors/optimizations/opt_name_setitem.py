# error: 'tuple[str,int] | None' does not support item assignment
def get() -> tuple[str, int] | None:
    return None


t = get()
t[0] = "b"
