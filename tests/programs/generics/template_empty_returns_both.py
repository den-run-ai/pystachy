# An empty list and an int, returned by a template whose literal argument chooses between them:
# the instance for pick(True) returns the list (once a rejection: tests/errors/inference's
# select_result_empty_flag.py keeps it where the argument is no literal).
def pick(flag):
    out = []
    if flag:
        return out
    return 5


print(pick(True))
