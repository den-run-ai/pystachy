# error: Problem() takes no keyword arguments
class Problem(Exception):
    pass


raise Problem(msg="x")
