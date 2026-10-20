# raise SystemExit() of a list | None that is None: status 0


def get(flag: bool) -> list[int] | None:
    return [1] if flag else None


print("before")
raise SystemExit(get(False))
