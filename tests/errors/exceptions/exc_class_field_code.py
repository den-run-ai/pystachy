# error: a field 'code' of exception class Quit is not supported: it would be SystemExit's own attribute code, which decides its exit status
class Quit(SystemExit):
    def __init__(self, why: str):
        super().__init__(why)
        self.code = 9


raise Quit("reason")
