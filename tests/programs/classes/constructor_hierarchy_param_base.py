# A hierarchy's class whose __init__ takes an object of an imported class that has a fixed
# layout and a constructor compiled for each call's argument types. The program never names that
# class's own subclass (as pathlib's _PurePathParents takes a PurePosixPath, whose subclass is
# PosixPath): the class is still an ordinary one, of one type whatever its constructor took.
from mods.constructor_hierarchy_views import Label, View, WideView


def describe(view: View) -> str:
    return view.describe()


labels: list[Label] = [Label(3), Label("x"), Label(2.5), Label([1, 2])]
print([label.shown() for label in labels], type(Label(1)) is type(Label("s")))
print(describe(View(labels[0])), describe(WideView(labels[1])))
