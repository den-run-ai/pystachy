"""Compare lookup fusion with a helper that invalidates the dictionary proof."""


def lookup(record: dict[str, int], key: str) -> int:
    if key in record:
        return record[key]
    return -2


def remove_key(record: dict[str, int], key: str) -> None:
    del record[key]


def lookup_after_update(record: dict[str, int], key: str) -> int:
    if key in record:
        remove_key(record, key)
        try:
            return record[key]
        except KeyError:
            return -1
    return -2


print(lookup({"reward": 7}, "reward"))
print(lookup_after_update({"reward": 7}, "reward"))
