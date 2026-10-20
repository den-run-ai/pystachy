# a field past the positional arguments raises IndexError once the arguments are evaluated and the
# fields before it are formatted; uncaught, it ends the program


class Loud:
    def __format__(self, spec: str) -> str:
        print("format", repr(spec))
        return "loud"


def arg(v: int) -> int:
    print("arg", v)
    return v


print("{0:>4}".format(arg(1)))
print("{0:x}{2}{1}".format(Loud(), arg(2)))
print("not reached")
