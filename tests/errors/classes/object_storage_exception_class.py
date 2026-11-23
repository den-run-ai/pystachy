# error: narrowing a value of object to type by isinstance() is not supported where it may hold an exception class (a type[BaseException]): test it with isinstance() of the classes it may be, or compare it with 'is' (making the table of type[BaseException] as object (for narrowing by isinstance() to type[object]), converted at tests/errors/classes/object_storage_exception_class.py:6)
# isinstance(x, type) of a value of object that may hold an exception class narrows it to no type:
# the class object of an exception class is exceptions.py's, which is no type[object]
# (object_exception_classes.py: what such a value of object does)
def main() -> None:
    values: list[object] = [ValueError, 1]
    for v in values:
        if isinstance(v, type):
            print(v.__name__)


main()
