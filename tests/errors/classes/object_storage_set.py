# error: set elements cannot be values of object: what each holds hashes and compares as its type does, which only the run time knows (narrow them with isinstance() first)
# a set whose elements are values of object
x: object = 1
print({x})
