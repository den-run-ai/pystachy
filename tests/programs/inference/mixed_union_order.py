"""Boxing and narrowing do not replay expressions or catch native errors."""
events: list[str] = []


def make(kind: str) -> int | list[int] | dict[str, int]:
    events.append(kind)
    if kind == "list":
        return [1]
    if kind == "dict":
        return {"a": 2}
    return 3


def index() -> int:
    events.append("index")
    return 4


def check() -> None:
    for kind in ["list", "dict", "number"]:
        value = make(kind)
        try:
            if isinstance(value, list):
                print(value[index()])
            elif isinstance(value, dict):
                print(value["missing"])
            else:
                print(value)
        except IndexError:
            print("IndexError")
        except KeyError:
            print("KeyError")
    print(events)


check()
