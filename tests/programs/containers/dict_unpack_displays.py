# Dict displays with ** (formerly rejected, tests/errors/containers/dict_unpack_*.py): of dicts, a new
# dict; of a **kwargs record, a record that prints as the dict CPython makes
print({"begin": "?", **{"sep": "-"}}, "x", "y")
a = {"x": 1}
b = {"y": 2}
c = {**a, **b}
print(c)


def show(d: dict[str, str]) -> None:
    print(d)


show(d={**{"color": "red"}})


def log(**f: str) -> None:
    print({**f})


log(sep="-", end="!\n")
print({**{"sep": "-"}, "end": "?\n"}, "x", "y")
print(len({**{"color": "red"}}))
print({**{"sep": "-"}}, "x", "y")
