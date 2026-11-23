# error: comparing values of object (in a list, tuple, in, count, index, sort, min or max) is not supported
# a search of a list of values of object: the runtime's searches do not reach their objects' types
xs: list[object] = [1, "a"]
print("a" in xs)
