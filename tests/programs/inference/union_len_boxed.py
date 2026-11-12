# len() of bytes, a dict, a set, a frozenset or a tuple[T, ...] is its first word, read
# directly. Stored as a union's int, that word needs no tag proof: PYSTACHY_IRCHECK=1
# rejected each of these boxes, also where the object may be None.
import json


def of_bytes(raw: bytes) -> "json.JSONValue":
    return len(raw)


def of_dict(table: dict[str, int]) -> int | str:
    return len(table)


def of_set(seen: set[int]) -> int | str:
    return len(seen)


def of_frozenset(seen: frozenset[str]) -> int | float | str:
    return len(seen)


def of_tuple(items: tuple[int, ...]) -> "json.JSONValue":
    return len(items)


def of_optional(raw: bytes | None) -> int | str:
    if raw is None:
        return "none"
    return len(raw)


def of_optional_dict(table: dict[str, int] | None) -> "json.JSONValue":
    if table is None:
        return None
    return len(table)


def record(raw: bytes, table: dict[str, int]) -> "dict[str, json.JSONValue]":
    details: dict[str, json.JSONValue] = {"bytes": len(raw), "keys": len(table)}
    details["text"] = raw.decode()
    details["sizes"] = [len(raw), len(table), len(raw) + len(table)]
    return details


def grow(table: dict[str, int], rounds: int) -> list[int | str]:
    sizes: list[int | str] = []
    for n in range(rounds):
        table["k" + str(n)] = n
        sizes.append(len(table))  # (read again after each store)
    sizes.append("done")
    return sizes


print(of_bytes(b""), of_bytes(b"abc"), of_bytes("hé".encode()))
print(of_dict({}), of_dict({"a": 1, "b": 2}))
print(of_set(set()), of_set({1, 2, 3}))
print(of_frozenset(frozenset(["x", "y"])))
print(of_tuple(()), of_tuple((4, 5, 6, 7)))
print(of_optional(None), of_optional(b"12345"))
print(of_optional_dict(None), of_optional_dict({"z": 0}))
print(json.dumps(record(b"hello", {"a": 1})))
print(grow({}, 3))


def total(values: "list[json.JSONValue]") -> int:
    result = 0
    for value in values:
        if isinstance(value, int):
            result += value
    return result


print(total([of_bytes(b"ab"), of_tuple((1, 2, 3)), "skipped", None]))
