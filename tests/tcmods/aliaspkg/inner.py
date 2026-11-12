from .consts import Row, Tag


def pick(tag: Tag) -> Row:
    if tag == "first":
        return {"a": 1}
    return [1, 2]
