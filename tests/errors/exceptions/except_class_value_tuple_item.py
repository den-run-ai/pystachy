# error: an except clause needs exception classes or a flat tuple of exception classes
# A tuple-valued item in a handler tuple display is nested too.
def run(kinds: tuple[type[BaseException], type[BaseException]]) -> None:
    try:
        raise ValueError("original")
    except (ValueError, kinds):
        print("incorrect match")


run((KeyError, OSError))
