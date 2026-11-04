def _Imported__pys_text_size(value: int) -> int:
    return value + 10


class Imported:
    def read(self, __pys_local: int) -> int:
        return __pys_text_size(__pys_local)
