class Type:
    def name(self) -> str:
        return "type"
def names(ts: tuple[Type, ...]) -> list[str]:
    return [t.name() for t in ts]
print(names((Type(), Type())))
