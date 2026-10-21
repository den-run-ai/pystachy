# tomli_w.dumps() of ports/tomli_w on tables: empty documents and tables, nested tables, keys
# that need quotes in table headers, and arrays of tables, which are written inline when each
# table fits on a line of 100 characters (upstream's heuristic) and as [[...]] tables otherwise.
# Many cases are upstream's tests/test_style.py, with values of one type in each container.
import tomli_w

# empty documents and tables (test_empty_doc, test_only_tables, test_dont_write_redundant_tables)
empty: dict[str, str] = {}
print(repr(tomli_w.dumps(empty)))
print(repr(tomli_w.dumps({"a": empty, "b": empty})))
print(repr(tomli_w.dumps({"outer": {"inner": empty}})))
print(repr(tomli_w.dumps({"tab1": {"tab2": {"tab3": empty}}})))

# nested tables, and keys that are quoted in the headers (test_tricky_keys, test_nested_keys)
print(tomli_w.dumps({"server": {"host": "localhost", "port": "8080"}, "client": {"name": "demo"}}))
print(tomli_w.dumps({"a": {"b": {"c": "deep"}}}))
print(tomli_w.dumps({"": {"": {"": 1}}, "a b": {"c.d": {"\u00e9": 2}}, "x": {"y": {"z": 3}}}))

# arrays of tables that stay inline: each table fits in 100 characters (test_array_of_short_tables,
# whose first line is 100 characters long), even where the same table comes twice
print(tomli_w.dumps({"fruit": [{"name": "apple"}, {"name": "banana"}]}))
print(tomli_w.dumps({"table": {"nested-array": [{"a" * 87: 0}, {"b": 1}, {"c": 2}]}}))
row = {"k0": "value number 0", "k1": "value number 1", "k2": "value number 2"}
print(tomli_w.dumps({"rows": [row, row]}))
print(tomli_w.dumps({"points": [{"pos": {"x": 1, "y": 2}}, {"pos": {"x": 3, "y": 4}}]}))
print(tomli_w.dumps({"rows": [empty, empty]}))
print(tomli_w.dumps({"tup": ({"k": "v"}, {"k": "w"})}))
print(tomli_w.dumps({"arrays": [[{"a": "b"}], []]}))

# arrays of tables written as [[...]]: a table of 101 characters, or a line break in one
print(tomli_w.dumps({"table": {"nested-array": [{"a" * 88: 0}, {"b": 1}]}}))
LONG = "x" * 120
print(tomli_w.dumps({"rows": [{"k": LONG}, {"k": "short"}]}))
print(tomli_w.dumps({"tup": ({"k": LONG}, {"k": "w"})}))
print(tomli_w.dumps({"aot": [{"multiline_string": "line1\nline2"}]}, multiline_strings=True))
print(tomli_w.dumps({"aot": [{"multiline_string": "line1\nline2"}]}))
# the 100 characters include the indent of the line (indent=): `{ k = "a...a" },` is n + 11
# characters, so 89 a's stay inline at indent=0 and 87 at indent=2, and none at indent=8
for indent in [0, 2, 8]:
    for n in [87, 88, 89, 90]:
        out = tomli_w.dumps({"t": [{"k": "a" * n}, {"k": "b"}]}, indent=indent)
        print(indent, n, "[[t]]" in out, len(out))
print(tomli_w.dumps({"t": [{"k": "a" * 89}]}, indent=0))
print(tomli_w.dumps({"t": [{"k": "a" * 90}]}, indent=0))

# arrays of tables nested in tables and in arrays of tables (test_array_of_tables_containing_lists,
# test_example_issue_12, test_non_trivial_nesting)
aot = {"aot": [{"a": [0, 1, 2, 3]}]}
print(tomli_w.dumps(aot))
print(tomli_w.dumps({"a": {"nested": aot}}))
print(tomli_w.dumps({"table": {"nested_table": [{"array_options": [1, 2, 3]}, {"another_array": [1, 2]}, {"c": [3]}]}}))
print(tomli_w.dumps({"rows": [{"sub": {"k": LONG}}, {"sub": {"k": "y"}}]}))
print(tomli_w.dumps({"a": [{"b": [{"c": LONG}]}]}))
print(tomli_w.dumps({"top": {"rows": [{"k": LONG}], "more": [{"k": LONG}, {"k": "z"}]}}))
empty_aot: dict[str, dict[str, list[dict[str, str]]]] = {"table": {"array": []}}
print(tomli_w.dumps(empty_aot))

# the order of the keys after one is deleted and set again, and another set again
order = {"a": {"x": 1}, "b": {"x": 2}, "c": {"x": 3}}
del order["a"]
order["a"] = {"x": 4}
order["b"] = {"x": 5}
print(tomli_w.dumps(order))

# 200 documents of random shapes (a linear congruential generator): tables of arrays of tables
# of ints, empty or not, inline or not, with keys that need quotes, at indents 0 to 5. Prints a
# checksum of their text and two of them.
state = 777


def rnd(n: int) -> int:
    global state
    state = (state * 1103515245 + 12345) % 2147483648
    return state % n


ALPH = 'abcxyz09-_ "\\\n.\t'


def rstr(maxlen: int) -> str:
    return "".join(ALPH[rnd(len(ALPH))] for _ in range(rnd(maxlen)))


check = 0
for it in range(200):
    doc: dict[str, dict[str, list[dict[str, int]]]] = {}
    for i in range(rnd(4)):
        sub: dict[str, list[dict[str, int]]] = {}
        for j in range(rnd(4)):
            tables: list[dict[str, int]] = []
            for q in range(rnd(4)):
                tb: dict[str, int] = {}
                for z in range(rnd(6)):
                    tb[rstr(25)] = rnd(1000000) - 500000
                tables.append(tb)
            sub[rstr(8)] = tables
        doc[rstr(6)] = sub
    out = tomli_w.dumps(doc, indent=rnd(6))
    for c in out:
        check = (check * 31 + ord(c)) % 1000000007
    if it == 3 or it == 150:
        print(out)
print(check)
