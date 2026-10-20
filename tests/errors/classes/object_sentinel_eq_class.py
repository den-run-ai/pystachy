# error: cannot compare object == C
# == between object()'s object and an object of a class: CPython calls the class's __eq__, where it
# has one, with the two swapped, which is not supported
class C:
    def __eq__(self, other):
        return True


print(object() == C())
