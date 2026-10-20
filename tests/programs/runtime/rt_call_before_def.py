def run() -> str:
    return late()


print("start")
print(run())


def late(s: str = "a" * 3) -> str:
    return s.upper()
