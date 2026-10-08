print("mods.counter: init", __name__)
count = 0
LIMIT = 3
log: list[str] = []


def incr(k: int) -> int:
    global count
    count += k
    if count > LIMIT:
        log.append(f"over {LIMIT}: {count}")
    return count


def describe() -> str:
    return f"{__name__}: count={count} limit={LIMIT} log={log}"


if __name__ == "__main__":
    import doctest
    print("not run when imported")
