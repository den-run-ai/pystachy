def report(msg: str, *, code: str = "misc") -> str:
    return f"{msg}[{code}]"
def fail(msg: str, **kwargs: str) -> str:
    return report(msg, **kwargs)
print(fail("x", code="syntax"))
