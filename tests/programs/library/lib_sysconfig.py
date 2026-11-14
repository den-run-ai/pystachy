# sysconfig (lib/sysconfig.py): what CPython and Pystachy answer alike. Each reports its own
# installation, so the program prints the names, the variables of the Python version and of
# every target, and what the paths and the variables must satisfy.
import os
import sys
import sysconfig

print(sysconfig.get_path_names())
print(sorted(sysconfig.get_paths()))
print(sysconfig.get_default_scheme() in sysconfig.get_scheme_names(),
      sysconfig.get_preferred_scheme('prefix') == sysconfig.get_default_scheme())
print(sysconfig.get_python_version(), sysconfig.is_python_build())

# the variables: of the version, of a build that is not free-threaded, of a 64-bit target
for name in ['py_version', 'py_version_short', 'py_version_nodot', 'py_version_nodot_plat', 'abiflags', 'abi_thread',
             'SIZEOF_SIZE_T', 'SIZEOF_VOID_P', 'Py_GIL_DISABLED', 'no_such_variable']:
    print(name, repr(sysconfig.get_config_var(name)))
config = sysconfig.get_config_vars()
print(config is sysconfig.get_config_vars(), 'prefix' in config, 'exec_prefix' in config, 'no_such_variable' in config)
print(config['SIZEOF_SIZE_T'] == sysconfig.get_config_var('SIZEOF_SIZE_T'), config['py_version_short'])
print(sysconfig.get_config_var('base') == os.path.normpath(sys.prefix),
      sysconfig.get_config_var('platbase') == os.path.normpath(sys.exec_prefix),
      sysconfig.get_config_var('installed_base') == os.path.normpath(sys.base_prefix),
      sysconfig.get_config_var('installed_platbase') == os.path.normpath(sys.base_exec_prefix))


def describe(name: str) -> str:
    # a variable by its type, as a caller narrows the union
    value = sysconfig.get_config_var(name)
    if value is None:
        return name + ' is not set'
    if isinstance(value, int):
        return name + ' is the int ' + str(value + 0)
    return name + ' is a str of ' + str(len(value.split('.'))) + ' parts'


print(describe('SIZEOF_SIZE_T'), describe('py_version'), describe('no_such_variable'), sep='; ')

# the paths: all absolute, the standard library's the directory of its modules
paths = sysconfig.get_paths()
print([os.path.isabs(paths[name]) for name in sorted(paths)])
print([sysconfig.get_path(name) == paths[name] for name in sysconfig.get_path_names()])
print(os.path.isfile(os.path.join(sysconfig.get_path('stdlib'), 'textwrap.py')),
      os.path.isdir(sysconfig.get_path('platstdlib')))
print(paths['data'] == sysconfig.get_config_var('base'), paths['scripts'] == os.path.join(paths['data'], 'bin'))
print(paths['purelib'].endswith('/site-packages'), paths['platlib'].endswith('/site-packages'))

# a caller's variables replace the configuration's; the paths are normalized
print(sysconfig.get_path('data', vars={'base': '/B/x/..'}), sysconfig.get_paths(vars={'base': '/B'})['scripts'])
print(sysconfig.get_path('scripts', 'posix_prefix', {'base': '/C//'}),
      sysconfig.get_paths('posix_prefix', {'base': ''})['data'])
print(sysconfig.get_paths(expand=False)['data'], sysconfig.get_path('scripts', expand=False),
      sysconfig.get_path('scripts', 'posix_prefix', None, False))

# unknown names
for attempt in range(4):
    try:
        if attempt == 0:
            sysconfig.get_paths('no_such_scheme')
        elif attempt == 1:
            sysconfig.get_path('no_such_path')
        elif attempt == 2:
            sysconfig.get_path('data', 'no_such_scheme')
        else:
            sysconfig.get_preferred_scheme('no_such_key')
    except KeyError as e:
        print('KeyError', e)

# a scheme's unexpanded paths are its own dict: a path of a variable that is not set is an
# error, unless the environment has all the variables of the path
scheme = sysconfig.get_paths('posix_prefix', expand=False)
print(scheme is sysconfig.get_paths('posix_prefix', expand=False), len(scheme))
for template in ['{no_such_variable}/x', '{base}/{no_such_variable}', '{PATH}/{no_such_variable}']:
    scheme['extra'] = template
    try:
        sysconfig.get_paths('posix_prefix')
    except AttributeError as e:
        print('AttributeError', e)
scheme['extra'] = '{PATH}'
print(sysconfig.get_path('extra', 'posix_prefix') == os.path.normpath(os.environ['PATH']),
      'extra' in sysconfig.get_paths('posix_prefix'))
scheme['extra'] = '{{base}}/{base}/{py_version_short}'
print(sysconfig.get_path('extra', 'posix_prefix', {'base': '/b'}))
del scheme['extra']
print(sorted(sysconfig.get_paths('posix_prefix')) == sorted(paths))
