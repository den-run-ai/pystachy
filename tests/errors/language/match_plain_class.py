# error: class patterns require a statically known dataclass
class Plain:
    def __init__(self) -> None:
        self.x = 1


match Plain():
    case Plain(x=x):
        print(x)
