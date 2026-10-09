# error: class method make() assigns its parameter 'cls', which names the class: not supported
class C:
    @classmethod
    def make(cls) -> int:
        cls = 1
        return cls
