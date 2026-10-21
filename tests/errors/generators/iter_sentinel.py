# error: iter(callable, sentinel) is not supported
def read() -> str:
    return ""


for line in iter(read, ""):
    print(line)
