# error: expected list[list[Base]], got list[list[Derived]]
class Base:
    pass


class Derived(Base):
    def only(self) -> str:
        return "derived"


inner = [Derived()]
src = [inner]
dst: list[list[Base]] = []
dst[:] = src
dst[0].append(Base())
print(inner[1].only())
