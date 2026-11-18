# A class is unbound until its class statement runs: reading it as a value before raises
# CPython's NameError, as a call of it does
def value() -> str:
    k = Later
    return k.__name__ + " " + str([Later])


def made() -> str:
    return Later().name()


for step in [1, 2]:
    try:
        print(value() if step == 1 else made())
    except NameError as e:
        print("NameError:", e)


class Later:
    def name(self) -> str:
        return "made"


print(value(), made())
