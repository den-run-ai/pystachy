# An exception class compared with an object of a class: type's __eq__ declines the object, so
# that CPython calls C.__eq__ with the class, as the right operand's reflected method, and compares
# them by identity where the class has no __eq__ (D)


class C:
    def __eq__(self, other: object) -> bool:
        return True


class D:
    pass


print(KeyError == C(), C() == KeyError, KeyError != C(), KeyError == D(), D() != KeyError)
