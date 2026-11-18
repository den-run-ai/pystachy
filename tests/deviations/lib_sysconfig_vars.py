# sysconfig's configuration variables are Pystachy's own: the ones CPython computes as it starts,
# for the Pystachy home and the Python version, and three that are true of every target. CPython
# adds the variables of its Makefile and pyconfig.h, about a thousand, with its executable's
# directory, user site directory and Makefile's directory: here each of those is not set.
# A dict of variables passed to get_paths() is left as it was; CPython adds every
# configuration variable to it.
import sys
import sysconfig

for name in sorted(sysconfig.get_config_vars()):
    value = sysconfig.get_config_var(name)
    print(name, 'the Pystachy home' if value == sys.prefix else repr(value))
for name in ['projectbase', 'userbase', 'srcdir', 'EXT_SUFFIX', 'SOABI', 'CC', 'LIBDIR', 'Py_DEBUG', 'SIZEOF_LONG']:
    print(name, sysconfig.get_config_var(name))
own = {'base': '/B'}
print(sysconfig.get_paths(vars=own)['scripts'], own)
