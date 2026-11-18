# a function Pystachy does not compile (eval), for tests/programs/classes/tuple_search_template_import.py,
# whose __eq__ calls it: a function of an imported module is compiled only where something calls it


def bad() -> bool:
    return eval("1") == 1
