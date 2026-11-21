# A configuration variable is an int, a str or None (not set): a method call selects the str's
# by the value's tag, as an int() or isinstance() would narrow it first.
import sysconfig

parts = sysconfig.get_config_var('py_version').split('.')
print(len(parts), parts[0], parts[1])
try:
    sysconfig.get_config_var('no_such_variable').split('.')
except AttributeError as e:
    print("AttributeError", e)
