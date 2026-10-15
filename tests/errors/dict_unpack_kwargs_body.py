# error: dict displays with ** are not supported
def log(**f: str) -> None:
    print({**f})
log(sep="-", end="!\n")
