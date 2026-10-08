def need(x: int) -> int:
    # raises ImportError where it is called, never as the module's code runs
    if x < 0:
        raise ImportError("negative")
    return x
