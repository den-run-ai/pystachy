# pystachy: python-int
# int(), %d and %x of a value of object in a module that opts in to promoting ints give a promoting
# int, past 64 bits too (a str's digits); float() and len() as in other modules
def main() -> None:
    values: list[object] = [2**70, 5, True, 2.5, "123456789012345678901234567890", None, [1]]
    for v in values:
        x: object = v
        try:
            print(int(x), "%d" % x, "%x" % x)
        except (TypeError, ValueError) as e:
            print(type(e).__name__, e)
        try:
            print(float(x), len(x))
        except (TypeError, ValueError, OverflowError) as e:
            print(type(e).__name__, e)


main()
