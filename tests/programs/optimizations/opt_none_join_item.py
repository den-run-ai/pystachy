# join() of a list of str | None items: an item that is None raises CPython's error
xs: list[str | None] = ["a", "b"]
print("-".join(xs))
xs.append(None)
print("-".join(xs))
