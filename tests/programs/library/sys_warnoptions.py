# sys.warnoptions: CPython's for a program run without -W options (tests/run.sh passes none, and
# tests/record.sh runs CPython without PYTHONWARNINGS), an empty list of str; every read is the
# same list, which the program can change in place, as warnings.py's _processoptions reads it
import sys
from sys import warnoptions


def show() -> None:
    print(sys.warnoptions, len(sys.warnoptions), bool(sys.warnoptions), sys.warnoptions == [])


def add(opt: str) -> None:
    sys.warnoptions.append(opt)


def churn(n: int) -> list[str]:
    # (it allocates while no variable holds the list, which lives on as sys.warnoptions)
    words = [""]
    for i in range(n):
        words = [str(i), "ignore::Warning:m" + str(i)]
    return words


def options() -> list[str]:
    return sys.warnoptions


def process(args: list[str]) -> int:
    n = 0
    for arg in args:
        print("option", arg.split(":"))
        n += 1
    return n


show()
add("error::DeprecationWarning")
add(churn(3000)[1])
show()
print(warnoptions is sys.warnoptions, options() is warnoptions, process(sys.warnoptions))
print("ignore" in sys.warnoptions, sys.warnoptions.index("error::DeprecationWarning"), sys.warnoptions[0].upper())
del sys.warnoptions[1:]
sys.warnoptions.insert(0, "default")
sys.warnoptions[1:1] = ["once"]
print(options(), repr(sys.warnoptions), str(warnoptions), sorted(sys.warnoptions))
sys.warnoptions.clear()
print(sys.warnoptions, options() is sys.warnoptions, process(warnoptions))
