# string.Formatter subclasses (lib/string.py, adapted) that override get_value(),
# check_unused_args(), format_field() and convert_field(); vformat() calls them in CPython's
# order. Each override compiles for every call's argument types, here all str
from string import Formatter


class Defaults(Formatter):
    def get_value(self, key, args, kwargs):
        if isinstance(key, str):
            return kwargs.get(key, "?")
        return Formatter.get_value(self, key, args, kwargs)


print(Defaults().format("{x}-{y}-{0}", "p", x="1"))


class Strict(Formatter):
    def check_unused_args(self, used_args, args, kwargs):
        print("used", len(used_args), sorted([str(u) for u in used_args]), "a" in used_args, 0 in used_args)
        for name in kwargs:
            if name not in used_args:
                raise ValueError("unused: " + name)


try:
    Strict().format("{a}", a="1", b="2")
except ValueError as e:
    print("ValueError", e)
print(Strict().format("{a}{b}{a}", a="1", b="2"), Strict().format("{0}{1}{0}", "x", "y"))


class Upper(Formatter):
    def format_field(self, value, format_spec):
        print("format_field", repr(value), repr(format_spec))
        return format(value, format_spec).upper()

    def convert_field(self, value, conversion):
        print("convert_field", repr(value), repr(conversion))
        if conversion == "u":
            return str(value).upper()
        return super().convert_field(value, conversion)


print(Upper().format("{0} {0!u} {1:>{2}}!", "ab", "cd", "4"))
try:
    Upper().format("{0!z}", "x")
except ValueError as e:
    print("ValueError", e)


class Logged(Formatter):
    def get_value(self, key, args, kwargs):
        print("get_value", repr(key))
        return super().get_value(key, args, kwargs)

    def parse(self, format_string):
        print("parse", repr(format_string))
        return super().parse(format_string)


print(Logged().vformat("{0:{1}}|{n!r}", ("é", ">3"), {"n": "m"}))
