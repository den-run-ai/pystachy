from decimal import Decimal, InvalidOperation


def compare(text: str, z: complex) -> None:
    value = Decimal(text)
    print(text, z)
    for operation in ["eq", "reflected eq", "ne", "reflected ne"]:
        try:
            if operation == "eq":
                print(value == z)
            elif operation == "reflected eq":
                print(z == value)
            elif operation == "ne":
                print(value != z)
            else:
                print(z != value)
        except InvalidOperation:
            print("invalid")


compare("1", 1 + 0j)
compare("1.5", 1.5 + 0j)
compare("1.1", 1.1 + 0j)
compare("9007199254740993", complex(9007199254740992, 0))
compare("-0", 0j)
compare("1", 1 + 2j)
compare("Infinity", complex(float("inf"), 0))
compare("NaN", 1 + 0j)
compare("sNaN", 1 + 2j)
compare("sNaN", 1 + 0j)
value = Decimal("1.5")
print(value in (1.5 + 0j,), 1.5 + 0j in (value,))
print((1j, 1.5 + 0j).index(value), (value, value).count(1.5 + 0j))
try:
    print(value < 1.5 + 0j)
except TypeError as error:
    print(error)
try:
    print(1.5 + 0j < value)
except TypeError as error:
    print(error)
