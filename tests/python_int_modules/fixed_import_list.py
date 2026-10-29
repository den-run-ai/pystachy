# Deliberately no opt-in: preserve python_int_import.py's original wide list display
# in a default module, in the program whose entry opts in to promoting ints.
from promoting_module import factorial


def show() -> None:
    value = factorial(30)
    print([value, value + 2])
