# int() of a str: CPython rejects more than 4300 digits in a base that is not a power of two, even
# for a small value; underscores, sign and spaces do not count, and the syntax is checked first
z = "0" * 4300
print(int(z[1:] + "7"), int(z + "1", 16), int("0x" + z + "1", 0), int("0b" + z, 0), int(z + "0", 32))
print(int("-" + z[1:] + "_9"), int(" " + z[1:] + "1 "), int(z + "\u0660", 8))
print(int(z + "7"))
