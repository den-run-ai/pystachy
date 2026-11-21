# As constructor_hierarchy_param_base.py, in a program that also makes an object of the
# parameter class's subclass: both are of the parameter's type, and the method called is the
# object's class's.
from mods.constructor_hierarchy_views import Label, LoudLabel, View, WideView


def describe(view: View) -> str:
    return view.describe()


print(describe(View(Label(3))), describe(WideView(LoudLabel("quiet"))), describe(View(LoudLabel(7))))
print(isinstance(LoudLabel(1), Label), isinstance(Label(1), LoudLabel))
