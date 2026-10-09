# error: deriving from SyntaxError is not supported
class BadInput(SyntaxError):
    pass


raise BadInput("x")
