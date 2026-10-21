# error: @classmethod on the special method __len__ is not supported
class C:
    @classmethod
    def __len__(cls) -> int:
        return 1
