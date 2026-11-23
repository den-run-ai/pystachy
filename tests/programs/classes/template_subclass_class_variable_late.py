# class variables of a class template read through objects of subclasses whose specializations
# only compiled code makes (template_subclass_class_variable.py: also those that declarations make)
class Style:
    default = "%"
    made = 0

    def __init__(self, fmt):
        self.fmt = fmt
        Style.made += 1

    def show(self) -> str:
        return self.default + str(self.fmt) + "/" + type(self).__name__ + "/" + str(self.made)


class Sub(Style):
    pass


class Loud(Style):
    default = "!"


def main() -> None:
    xs = [Style("a"), Sub("b"), Loud("c")]
    ys = [Style(1.5), Sub(2.5), Loud(3.5)]
    zs = [Loud(1), Sub(2), Style(3)]
    print(" ".join([x.show() for x in xs]), "|", " ".join([y.show() for y in ys]), "|", " ".join([z.show() for z in zs]))
    Style.default = "@"
    print(" ".join([x.show() for x in xs]), "|", " ".join([y.show() for y in ys]), "|", " ".join([z.show() for z in zs]))
    print(xs[2].made, ys[2].made, zs[0].made, xs[2].default, Loud.default, Style.made)


main()
