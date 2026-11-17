# Documented deviation (#1504): an optional import whose except clause's as name is a name its
# imports bind (except ImportError as json) keeps today's form, so a subclass of ImportError that
# the statements after the imports raise ends the program. Keeping the clauses would leave json
# bound to the module after the handler, where CPython unbinds it: CPython prints 0, then
# "NameError name 'json' is not defined".
class Missing(ImportError):
    pass


def get(ok: bool) -> int:
    if not ok:
        raise Missing("gone")
    return 1


try:
    import json

    v = get(False)
except ImportError as json:
    v = 0
print(v)
try:
    print(json.dumps([v]))
except NameError as err:
    print("NameError", err)
