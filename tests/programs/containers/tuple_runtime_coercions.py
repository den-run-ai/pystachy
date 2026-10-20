string_values: tuple[str | None, ...] = tuple("abc")
integers: list[int] = [1, 2, 3]
integer_values: tuple[int | None, ...] = tuple(integers)
integers[0] = 99
floats: list[float] = [0.5, -1.5]
float_values: tuple[float | None, ...] = tuple(floats)
floats[0] = 99.5
booleans: list[bool] = [True, False]
boolean_values: tuple[bool | None, ...] = tuple(booleans)
booleans[0] = False

def choose(present: bool) -> tuple[str, ...] | None:
    return ("a", "b") if present else None

for i in range(100):
    garbage = [str(i) * 32, "temporary" + str(i)]
print("strings", string_values, repr(string_values), len(string_values), string_values[0])
print("integers", integer_values, repr(integer_values), len(integer_values), integer_values[0])
print("floats", float_values, repr(float_values), len(float_values), float_values[0])
print("booleans", boolean_values, repr(boolean_values), len(boolean_values), boolean_values[0])
for present in [False, True]:
    result = choose(present)
    if result is None:
        print("absent")
    else:
        print("present", result, repr(result), len(result), result[0], result[-1])
