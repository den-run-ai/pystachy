# error: closed union method calls require narrowing with isinstance() first
# A configuration variable is an int, a str or None (not set): a caller narrows the value with
# isinstance(), or converts it with int(), str() or bool(), before using it as one of them.
import sysconfig

print(sysconfig.get_config_var('py_version').split('.'))
