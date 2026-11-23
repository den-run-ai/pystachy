# A class template under a class that derives from another (#962): Leaf's specializations derive
# from Mid, which derives from Root, so that a list of Root holds them; Leaf's body binds Root's
# class attribute label again, which its objects read.
class Root:
    label = "root"

    def __init__(self) -> None:
        self.tag = "root"

    def who(self) -> str:
        return "root " + self.tag


class Mid(Root):
    def who(self) -> str:
        return "mid " + self.tag


class Leaf(Mid):
    label = "leaf"

    def __init__(self, v):
        super().__init__()
        self.v = v

    def who(self) -> str:
        return "leaf " + str(self.v) + " " + super().who()


rs: list[Root] = [Root(), Mid(), Leaf(1), Leaf("x")]
for r in rs:
    print(r.who(), isinstance(r, Mid), isinstance(r, Leaf), r.label)
m: Mid = Leaf(2.5)
m.tag = "set"
print(m.who())
