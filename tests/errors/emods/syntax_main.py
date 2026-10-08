def f() -> int:
    return 1


if __name__ == "__main__":
    async with f():
        pass
