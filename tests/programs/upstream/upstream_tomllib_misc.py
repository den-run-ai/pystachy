# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.
#
# CPython 3.13.16's Lib/test/test_tomllib/test_error.py and test_misc.py, their unittest scaffolding
# made functions and assertions. Not here: test_misc's test_load and test_incorrect_load (binary
# and text files given to load(): Pystachy has no binary files), test_parse_float (decimal.Decimal,
# here a function of the program's), test_deepcopy (copy.deepcopy), and the recursion limits of
# test_inline_array_recursion_limit and test_inline_table_recursion_limit (test.support's), whose
# nesting is a fixed depth here; test_module_name reads the class's __module__, not an object's
import datetime
import tomllib
from typing import Any


def decode_error(doc: str) -> str:
    try:
        tomllib.loads(doc)
    except tomllib.TOMLDecodeError as e:
        return str(e)
    raise AssertionError("no TOMLDecodeError")


# test_error.TestError.test_line_and_col
assert decode_error("val=.") == "Invalid value (at line 1, column 5)"
assert decode_error(".") == "Invalid statement (at line 1, column 1)"
assert decode_error("\n\nval=.") == "Invalid value (at line 3, column 5)"
assert decode_error("\n\n.") == "Invalid statement (at line 3, column 1)"
# test_error.TestError.test_missing_value
assert decode_error("\n\nfwfw=") == "Invalid value (at end of document)"
# test_error.TestError.test_invalid_char_quotes
assert " '\\n' " in decode_error("v = '\n'")
# test_error.TestError.test_module_name
assert tomllib.TOMLDecodeError.__module__ == tomllib.__name__
print("test_error: 4 of 5 (test_invalid_parse_float: lib_tomllib_dynamic.py)")


# test_misc.TestMiscellaneous.test_parse_float, with a function in place of decimal.Decimal
def tagged(s: str) -> str:
    return "F" + s


doc = """
      val=0.1
      biggest1=inf
      biggest2=+inf
      smallest=-inf
      notnum1=nan
      notnum2=-nan
      notnum3=+nan
      """
obj = tomllib.loads(doc, parse_float=tagged)
print(obj)
assert obj["val"] == "F0.1" and obj["notnum2"] == "F-nan" and obj["biggest2"] == "F+inf"

# test_misc.TestMiscellaneous.test_deepcopy's document and expected object, compared directly
obj = tomllib.loads("""
      [bliibaa.diibaa]
      offsettime=[1979-05-27T00:32:00.999999-07:00]
      """)
expected = datetime.datetime(1979, 5, 27, 0, 32, 0, 999999, tzinfo=datetime.timezone(datetime.timedelta(hours=-7)))
assert obj["bliibaa"]["diibaa"]["offsettime"][0] == expected
print(obj)

# test_inline_array_recursion_limit and test_inline_table_recursion_limit, at a fixed depth
nest_count = 40
print(tomllib.loads("arr = " + nest_count * "[" + nest_count * "]")["arr"][0][0][0])
table = tomllib.loads(nest_count * "key = {" + nest_count * "}")
depth = 0
cur: Any = table
while "key" in cur:
    cur = cur["key"]
    depth += 1
print(depth)

# test_misc.TestMiscellaneous.test_key_recursion_limit: a key of more parts than
# tomllib._parser.MAX_KEY_PARTS (sys.getrecursionlimit()) is a RecursionError; one of fewer parts
# parses, here 100 rather than the limit's less 2, whose tables each part checks
print(tomllib._parser.MAX_KEY_PARTS)
def key_depth(v, n: int) -> int:
    # (the tables a dotted key made, down to its value: a parameter, as each level's value is an
    # Any value of its own type)
    if isinstance(v, dict):
        return key_depth(v["a"], n + 1)
    print(v)
    return n


print(key_depth(tomllib.loads("a." * 100 + "a = 1"), 0))
nest_count = tomllib._parser.MAX_KEY_PARTS + 2
nested_key_toml = "a." * nest_count + "a = 1"
try:
    tomllib.loads(nested_key_toml)
    raise AssertionError("no RecursionError")
except RecursionError as e:
    print("RecursionError:", e)
