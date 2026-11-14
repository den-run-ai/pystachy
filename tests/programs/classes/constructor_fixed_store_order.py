class AnnotatedSecond:
    def __init__(self, value):
        if isinstance(value, int):
            self.value = value
        else:
            self.value: int = len(value)


class AnnotatedFirst:
    def __init__(self, value):
        if isinstance(value, int):
            self.value: int = value
        else:
            self.value = len(value)


print(AnnotatedSecond(3).value, AnnotatedSecond("hello").value)
print(AnnotatedFirst(3).value, AnnotatedFirst("hello").value)
