# error: expected float | None, got str
# pystachy: dynamic-any
values: list[float | None] = [None]
values.append("wrong")
