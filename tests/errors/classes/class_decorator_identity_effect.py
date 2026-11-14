# error: unsupported decorator @mypyc_attr
# (an argument that is no constant runs code where CPython creates the class: not an identity)
from mypy_extensions import mypyc_attr


def option() -> bool:
    print("evaluated")
    return True


@mypyc_attr(allow_interpreted_subclasses=option())
class A:
    pass


print(A())
