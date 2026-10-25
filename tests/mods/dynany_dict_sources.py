# Deliberately ordinary typed mode: a Dynamic Any importer shares its hash
# scheme even when this module is compiled without the pragma.
def fresh():
    return {}


def sources() -> list[dict[int, list[str]]]:
    literal = {0: ['zero']}
    opened = {}
    opened[0] = ['zero']
    late: dict[int, list[str]] = fresh()
    late[0] = ['zero']
    comp = {i: ['zero'] for i in range(1)}
    keys = dict.fromkeys([0], ['zero'])
    dict_keys = dict.fromkeys(literal, ['zero'])
    copied = literal.copy()
    constructed = dict(literal)
    updated: dict[int, list[str]] = {}
    updated.update(literal)
    united = literal | opened
    holes = {i: ['zero'] for i in range(12)}
    for i in range(1, 12):
        del holes[i]
    sparse_copy = holes.copy()
    sparse_dict = dict(holes)
    del holes[0]
    holes[0] = ['zero']
    return [literal, opened, late, comp, keys, dict_keys, copied, constructed,
            updated, united, holes, sparse_copy, sparse_dict]
