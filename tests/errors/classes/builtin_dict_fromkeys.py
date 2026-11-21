# error: type object 'Made' has no attribute 'fromkeys'
class Made(dict[str, int]):
    pass


print(Made.fromkeys(["a"], 1))
