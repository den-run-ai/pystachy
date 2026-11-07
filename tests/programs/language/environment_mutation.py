# Direct environment updates must agree with getenv and reach child processes.
import os

name = "PYSTACHY_TEST_ENVIRONMENT_MUTATION"
print(os.environ.pop(name, "initially absent"))
print(os.environ.__setitem__(name, "child one"))
print(os.getenv(name))
print(os.system('test "$PYSTACHY_TEST_ENVIRONMENT_MUTATION" = "child one"'))
os.environ.__setitem__(name, "replacement")
print(os.getenv(name), os.environ.pop(name, "missing"), os.getenv(name, "missing"))
print(os.system('test "${PYSTACHY_TEST_ENVIRONMENT_MUTATION+x}" != x'))
os.environ.__setitem__(name, "")
print(repr(os.getenv(name, "missing")), repr(os.environ.pop(name, "missing")))
fallback = "default " + str(len(name))
print(os.environ.pop(name, fallback) is fallback)

for key, value in [("", "value"), ("a=b", "value"), ("a\x00b", "value"),
                   (name, "value\x00tail"), ("a=b", "\x00")]:
    try:
        os.environ.__setitem__(key, value)
    except (ValueError, OSError) as error:
        print(type(error).__name__, str(error))
for key in ["", "a=b", "a\x00b"]:
    print(os.environ.pop(key, "missing"), os.getenv(key, "missing"))
# A libc getenv call alone would mistakenly treat this as a name containing '='.
os.environ.__setitem__(name, "tail=value")
print(os.environ.pop(name + "=tail", "missing"), os.getenv(name + "=tail", "missing"))
print(os.environ.pop(name, "missing"))

for key, value in [(name + "é", "éléphant 漢字"),
                   (name + "\udcff", "a\udc80\udcffz")]:
    os.environ.__setitem__(key, value)
    print(repr(os.getenv(key)), repr(os.environ.pop(key, "missing")), os.getenv(key, "missing"))
for key, value in [(name + "\ud800", "value"), (name, "\ud800")]:
    try:
        os.environ.__setitem__(key, value)
    except UnicodeEncodeError as error:
        print(type(error).__name__, str(error))
try:
    print(os.getenv(name + "\ud800", "missing"))
except UnicodeEncodeError as error:
    print(type(error).__name__, str(error))
try:
    print(os.environ.pop(name + "\ud800", "missing"))
except UnicodeEncodeError as error:
    print(type(error).__name__, str(error))
print(os.getenv(name, "finally absent"))
