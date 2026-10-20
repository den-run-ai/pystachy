# error: name 'Later' is not defined (CPython evaluates this annotation when the annotated assignment runs
while True:
    v: Later | None = None
    break


class Later:
    pass


print(v)
