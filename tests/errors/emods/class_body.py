def note(s: str) -> int:
    print("note:", s)
    return 1


class Table:
    width = note("width")

    def cell(self, i):
        return i
