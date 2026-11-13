# Can a dict hold bool, str and two kinds of lists (ast_serialize's fifth result element)?
Value = bool | str | list[tuple[int, list[str]]] | list[tuple[int, str]]


def make() -> dict[str, Value]:
    d: dict[str, Value] = {}
    d["is_partial_package"] = False
    d["mypy_ignores"] = [(1, ["x"])]
    d["source_hash"] = "abc"
    d["mypy_comments"] = [(2, "y")]
    return d


d = make()
print(d["is_partial_package"], d["source_hash"], d["mypy_ignores"], d["mypy_comments"])
print(d)
