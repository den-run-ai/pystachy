# error: runtime-length tuple elements must be int, float, bool, str or their optional types, or objects of the program's classes (not exceptions or NamedTuples)
# exception objects are not such items yet
class Problem(Exception):
    pass


problems: tuple[Problem, ...] = (Problem("a"), Problem("b"))
print(len(problems))
