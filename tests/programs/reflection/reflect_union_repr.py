# str() and repr() of a reference union of classes (#486): each object as its own class prints
# it, chosen by the union's member tag (and an object's class tag)
class Cat:
    pass


class Dog:
    def __repr__(self) -> str:
        return "Dog()"

    def __str__(self) -> str:
        return "a dog"


class Puppy(Dog):
    def __repr__(self) -> str:
        return "Puppy()"


pets: list[Cat | Dog] = [Cat(), Dog(), Puppy()]
for p in pets:
    print(repr(p).split(" object at ")[0], str(p).split(" object at ")[0])
maybe: Cat | Dog | None = None
print(repr(maybe), str(maybe))
maybe = Dog()
print(repr(maybe), f"{maybe}")
