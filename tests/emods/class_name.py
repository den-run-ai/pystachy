class Named:
    __name__: str = "custom"

    def name(self, n: str = __name__) -> str:
        return n
