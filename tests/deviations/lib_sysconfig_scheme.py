# sysconfig's install scheme is Pystachy's own: the one layout of the Pystachy home (sys.prefix),
# whose standard library is its lib/, without a directory of the implementation and version.
# CPython has nine schemes, and its default one's paths are of its installation, such as
# /usr/lib/python3.13 and /usr/lib/python3.13/site-packages. There is no home, user or virtual
# environment scheme: asking for one is an error, as on a CPython platform without it.
import sys
import sysconfig

print(sysconfig.get_scheme_names(), sysconfig.get_default_scheme())
paths = sysconfig.get_paths()
for name in sorted(paths):
    print(name, paths[name].startswith(sys.prefix), repr(paths[name][len(sys.prefix):]))
print(sysconfig.get_paths(expand=False)['stdlib'], sysconfig.get_paths(expand=False)['purelib'])
for key in ['home', 'user']:
    try:
        sysconfig.get_preferred_scheme(key)
    except ValueError as e:
        print('ValueError', e)
for scheme in ['posix_home', 'posix_user', 'venv']:
    try:
        sysconfig.get_paths(scheme)
    except KeyError as e:
        print('KeyError', e)
