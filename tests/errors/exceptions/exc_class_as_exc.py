# error: expected a builtin exception, got an object of Problem (annotate it with Problem or a base class of the program)
class Problem(Exception):
    pass


errors: list[Exception] = []
errors.append(Problem("x"))
