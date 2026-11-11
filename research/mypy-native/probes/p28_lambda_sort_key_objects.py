# sorted(..., key=lambda) over objects and tuple keys (133 sorted calls)
class Err:
    def __init__(self, file: str, line: int) -> None:
        self.file = file
        self.line = line
errs = [Err("b", 2), Err("a", 9), Err("a", 1)]
print([(e.file, e.line) for e in sorted(errs, key=lambda e: (e.file, e.line))])
