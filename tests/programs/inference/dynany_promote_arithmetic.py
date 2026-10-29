# No opt-in here: the python-int gate promotes the accumulator and typed operand.
import provenints

total = 1000
number = 6
for value in provenints.values():
    if isinstance(value, int):
        print("orders", type(value).__name__, number + value, value + number)
        total += value
        print("accumulator", total)
        print("bitwise", number & value, value & number, number | value, value | number, number ^ value, value ^ number)
        print("result types", type(number & value).__name__, type(value | number).__name__, type(number ^ value).__name__)
    else:
        print("non-int", type(value).__name__, value)

# Two dynamically proven bools still produce bools for bitwise operations.
left = provenints.yes()
right = provenints.no()
if isinstance(left, int) and isinstance(right, int):
    print("bool bitwise", left & right, left | right, left ^ right)
    print("bool types", type(left & right).__name__, type(left | right).__name__, type(left ^ right).__name__)
