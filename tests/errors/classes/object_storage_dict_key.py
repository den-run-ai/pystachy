# error: dict keys cannot be values of object: what each holds hashes and compares as its type does, which only the run time knows (narrow them with isinstance() first)
# a dict whose keys are values of object
x: object = 1
d = {x: "one"}
print(d)
