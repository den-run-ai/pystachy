# error: an except clause needs exception classes or a flat tuple of exception classes
# CPython rejects a nested tuple even if an exception class inside it would match.
def run(kinds: tuple[tuple[type[BaseException], type[BaseException]], type[BaseException]]) -> None:
    try:
        raise ValueError("original")
    except kinds:
        print("incorrect match")


run(((ValueError, KeyError), OSError))
