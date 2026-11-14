class Imported(Exception):
    def text(self) -> str:
        return super().__str__()

    def representation(self) -> str:
        return super(Imported, self).__repr__()
