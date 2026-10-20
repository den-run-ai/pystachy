# string.Template with keyword arguments of different types (formerly rejected,
# tests/errors/lib_string_kwargs_types.py): each placeholder's name is looked up in the
# **kwargs record as it runs, giving a value of the union of their types
from string import Template

print(Template("$name has $count").substitute(name="Ann", count=3))
t = Template("${who}: $n items at $price, $flag")
print(t.substitute(who="é", n=2, price=1.5, flag=None))
print(t.safe_substitute({"who": "map"}, n=7, price=0.25))
try:
    print(t.substitute(who="x", n=1))
except KeyError as e:
    print("KeyError", e)
