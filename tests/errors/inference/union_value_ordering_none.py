# error: '<' not supported between instances of float | int | None and str (no member of the closed union has that ordering)
# Neither a number nor None is ordered with a str: an error, as int < str is.
def before(x: int | float | None) -> bool:
    return x < "a"


print(before(1))
