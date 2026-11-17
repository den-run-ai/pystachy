# error: runtime-length tuple elements must be int, float, bool, str or their optional types, or objects of one of the program's classes (not an exception, a NamedTuple or a union of classes)
# exception objects are not such items yet
class Problem(Exception):
    pass


problems: tuple[Problem, ...] = (Problem("a"), Problem("b"))
print(len(problems))
