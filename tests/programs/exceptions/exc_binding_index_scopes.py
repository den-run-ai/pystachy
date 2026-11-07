# Nested definitions do not contribute bindings from their bodies to the outer
# function. Compiling a template in a handler must not replace the outer index.
def nested(value):
    try:
        raise ValueError("template")
    except ValueError as target:
        print(target)
    target = value
    return target


def outer() -> None:
    try:
        raise ValueError("first")
    except ValueError as target:
        print(target, nested(5))

    def hidden() -> int:
        target = 7
        return target

    try:
        raise ValueError("second")
    except ValueError as another:
        print(another, hidden())
    try:
        print(target)
    except UnboundLocalError:
        print("outer target deleted")


outer()

try:
    raise ValueError("module")
except ValueError as module_target:
    print(module_target)
module_target = 9
print(module_target)
