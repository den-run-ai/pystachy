# error: expected int, got float
# range.index() and range.count() take an int (CPython also searches for an equal float)
print(range(3).count(1.0))
