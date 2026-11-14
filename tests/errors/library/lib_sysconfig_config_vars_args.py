# error: get_config_vars() takes 0 positional arguments but 2 were given
# get_config_vars() returns the dict of the variables. With names, CPython's returns the list
# of their values instead: a function has one return type here, and get_config_var() reads one.
import sysconfig

print(sysconfig.get_config_vars('prefix', 'exec_prefix'))
