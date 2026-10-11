# error: dict.update() of a dict[str,int | None] takes a dict of its type, a list[tuple[str,int | None]] or keyword arguments, not dict[str,int]
# a dict of other key or value types: d's values are not o's
d: dict[str, int | None] = {"a": None}
o = {"b": 2}
d.update(o)
