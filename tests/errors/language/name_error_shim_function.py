# error: name 'unicode' is not defined
# (in a function: decided only at a module's top level)
def text_type() -> str:
    try:
        return unicode  # noqa: F821
    except NameError:
        return "str"


print(text_type())
