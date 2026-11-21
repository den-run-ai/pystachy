# error: sequence patterns require a tuple or list subject, got Stack
class Stack(list[int]):
    pass


def kind(v: Stack) -> str:
    match v:
        case []:
            return "empty"
        case [x]:
            return "one"
    return "more"


print(kind(Stack()))
