# A shared scope index must preserve the deletion of both the handler's temporary
# binding and any other binding of its name, through every way out of the handler.
def loop_exit(mode: int) -> None:
    message = "before"
    for i in range(2):
        try:
            raise ValueError(str(i))
        except ValueError as message:
            print("loop", mode, message)
            if mode == 0:
                continue
            break
    try:
        print(message)
    except UnboundLocalError:
        print("loop target deleted", mode)


def returned() -> str:
    message = "before"
    try:
        try:
            raise ValueError("return")
        except ValueError as message:
            return str(message)
    finally:
        try:
            print(message)
        except UnboundLocalError:
            print("return target deleted")


def nested_targets() -> None:
    try:
        raise ValueError("outer")
    except ValueError as first:
        try:
            raise ValueError("different")
        except ValueError as second:
            print(first, second)
        print("outer remains", first)
        try:
            raise ValueError("same")
        except ValueError as first:
            print(first)
        try:
            print(first)
        except UnboundLocalError:
            print("inner deleted outer target")


loop_exit(0)
loop_exit(1)
print(returned())
nested_targets()
