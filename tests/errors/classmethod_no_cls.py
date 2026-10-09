# error: method 'make' of class 'C' must take cls as its first parameter
class C:
    @classmethod
    def make() -> int:
        return 1
