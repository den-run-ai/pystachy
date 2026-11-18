# type(x) and x.__class__ of an object are its class's class object, a value (#7): kept, compared,
# called (type(self)(...) makes an object of the object's own class) and used as a key. type(x)
# of an x that is None is NoneType's class object, whose call makes None
class Widget:
    def __init__(self, label: str = "w") -> None:
        self.label = label

    def clone(self) -> "Widget":
        return type(self)(self.label + "+")

    def fresh(self) -> "Widget":
        return self.__class__()

    def kind(self) -> str:
        return self.__class__.__name__ + "/" + type(self).__qualname__

    @classmethod
    def me(cls) -> str:
        k = cls
        return k.__name__ + " " + str(k)


class Button(Widget):
    pass


class Slider(Widget):
    def __init__(self, label: str = "s") -> None:
        super().__init__(label.upper())


class Box:
    def __init__(self, v: int) -> None:
        self.v = v


def kind_of(x: Widget | None) -> str:
    t = type(x)
    return t.__name__ + " " + str(t) + " " + str(t is Widget) + " " + str(t == Slider)


def remake(x: Widget | None) -> Widget | None:
    return type(x)()


def name(k: type[Widget] | None) -> str:
    try:
        return k.__name__
    except AttributeError as e:
        return "AttributeError: " + str(e)


def arg(x: Box | None) -> str:
    try:
        b = type(x)(7)
        return "made " + str(b.v if b is not None else -1)
    except TypeError as e:
        return "TypeError: " + str(e)


t = type(Button("b"))
print(t, t is Button, t.__name__, t("made").label, type(t("x")) is t)
ws: list[Widget] = [Slider("a"), Button("b"), Widget("plain")]
for w in ws:
    c = w.clone()
    n = w.fresh()
    print(w.kind(), c.kind(), c.label, n.kind(), n.label, type(c) is type(w), c.__class__ is w.__class__, w.__class__)
print(Widget.me(), "|", Button.me(), "|", Slider.me())
print(kind_of(Widget()), "|", kind_of(Slider()), "|", kind_of(None))
print(remake(None), type(remake(Slider())).__name__, isinstance(remake(Widget()), Widget))
print(name(Button), name(None), arg(None), arg(Box(1)))
print(isinstance(None, type(None)), isinstance(Widget(), type(None)))
counts: dict[type[Widget], list[str]] = {}
for w in ws + [w.clone() for w in ws]:
    counts.setdefault(type(w), []).append(w.label)
print({k.__name__: v for k, v in counts.items()})
