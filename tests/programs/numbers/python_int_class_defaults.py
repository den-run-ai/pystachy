# pystachy: python-int
# A small literal override retains its inherited promoting class/instance field layout.
class Parent:
    count: int = 2 ** 70


class Child(Parent):
    count = 3


class Grandchild(Child):
    count = 2 ** 80


def count(obj: Parent) -> int:
    return obj.count


print(Parent.count, Child.count, Grandchild.count)
print(count(Parent()), count(Child()), count(Grandchild()))
child = Child()
child.count = 2 ** 90
print(count(child), count(Child()), Parent.count, Child.count)
