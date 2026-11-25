# A base-typed location holding a deeper subclass dispatches an inherited class method
# on the actual object. This case happened to match before #1744 because Deep reused Style.tag.
class Style:
    tag = "plain"

    def __init__(self, fmt):
        self.fmt = fmt

    @classmethod
    def kind(cls) -> str:
        return cls.tag


class Mid(Style):
    tag = "mid"


class Deep(Mid):
    tag = "plain"


xs = [Mid(1)]
xs[0] = Deep(2)
print(xs[0].kind())
