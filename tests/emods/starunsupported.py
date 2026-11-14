def report(msg: str, **kwargs: memoryview) -> str:
    return msg


def collect(*args: memoryview) -> int:
    return len(args)
