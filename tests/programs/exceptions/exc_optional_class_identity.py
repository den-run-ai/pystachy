# User exception annotations include None as a plain pointer; caught optional
# exceptions use nullable Exc wrappers. Compare both without reading a null wrapper.
class Child(ValueError):
    pass


def compare(caught: BaseException | None, user: Child | None) -> None:
    print(caught is user, user is caught)
    print(caught is not user, user is not caught)


def only_none(left: BaseException | None, right: Child | None) -> None:
    print(left is right, right is left, left is not right, right is not left)


original = Child("same")
different = Child("same")
error: BaseException | None = None
nullable: Child | None = None
compare(error, nullable)
compare(error, original)
only_none(None, None)
try:
    raise original
except BaseException as caught:
    error = caught
compare(error, original)
compare(error, different)
compare(error, nullable)
nullable = original
compare(error, nullable)
error = None
compare(error, nullable)
