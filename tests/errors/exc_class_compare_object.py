# error: exc_class_compare_object.py:10: error: comparing an exception class with C is not supported
# CPython calls C.__eq__ with the class, as the right operand's reflected method


class C:
    def __eq__(self, other: object) -> bool:
        return True


print(KeyError == C())
