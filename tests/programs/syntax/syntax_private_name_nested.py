# These dormant templates exercise lexical checks for nested classes, which still have no
# native representation. A nested private class starts a context from its source class name.
def dormant(unused):
    _Outer__value = 1
    _Inner__value = 2

    class Outer:
        def method(self):
            nonlocal __value
            return __value

        class __Inner:
            def method(self):
                nonlocal __value
                return __value


print("nested private scopes parsed")
