# SPDX-License-Identifier: MIT
# SPDX-FileCopyrightText: 2021 Taneli Hukkinen
# Licensed to PSF under a Contributor Agreement.
#
# CPython 3.13.16's Lib/test/test_tomllib/test_data.py over its data (Lib/test/test_tomllib/data,
# whose 62 .toml files are written out below, as their bytes decode): each valid document's
# result, which the recording compares with CPython's own tomllib, where test_valid compares it
# with the .json beside it, and each invalid one's TOMLDecodeError (test_invalid)
import tomllib

DOCS: list[tuple[str, str]] = [
    ('invalid/array-missing-comma.toml', 'arrr = [true false]\n'),
    ('invalid/array-of-tables/overwrite-array-in-parent.toml', '[[parent-table.arr]]\n[parent-table]\nnot-arr = 1\narr = 2\n'),
    ('invalid/array-of-tables/overwrite-bool-with-aot.toml', 'a=true\n[[a]]'),
    ('invalid/array/file-end-after-val.toml', 'a=[1'),
    ('invalid/array/unclosed-after-item.toml', 'v=[1,'),
    ('invalid/array/unclosed-empty.toml', 'v=['),
    ('invalid/basic-str-ends-in-escape.toml', '"backslash is the last char\\'),
    ('invalid/boolean/invalid-false-casing.toml', 'val=falsE'),
    ('invalid/boolean/invalid-true-casing.toml', 'val=trUe'),
    ('invalid/dates-and-times/invalid-day.toml', '"only 28 or 29 days in february" = 1988-02-30\n'),
    ('invalid/dotted-keys/access-non-table.toml', 'a = false\na.b = true'),
    ('invalid/dotted-keys/extend-defined-aot.toml', '[[tab.arr]]\n[tab]\narr.val1=1\n'),
    ('invalid/dotted-keys/extend-defined-table-with-subtable.toml', '[a.b.c.d]\n  z = 9\n[a]\n  b.c.d.k.t = 8\n'),
    ('invalid/dotted-keys/extend-defined-table.toml', '[a.b.c]\n  z = 9\n[a]\n  b.c.t = 9\n'),
    ('invalid/inline-table-missing-comma.toml', 'arrr = { comma-missing = true valid-toml = false }\n'),
    ('invalid/inline-table/define-twice-in-subtable.toml', 'table1 = { table2.dupe = 1, table2.dupe = 2 }'),
    ('invalid/inline-table/define-twice.toml', 'table = { dupe = 1, dupe = 2 }'),
    ('invalid/inline-table/file-end-after-key-val.toml', 'a={b=1'),
    ('invalid/inline-table/mutate.toml', 'a = { b = 1 }\na.b = 2'),
    ('invalid/inline-table/override-val-in-table.toml', '[tab.nested]\ninline-t = { nest = {} }\n\n[tab]\nnested.inline-t.nest = 2\n'),
    ('invalid/inline-table/override-val-with-array.toml', 'inline-t = { nest = {} }\n\n[[inline-t.nest]]\n'),
    ('invalid/inline-table/override-val-with-table.toml', 'inline-t = { nest = {} }\n\n[inline-t.nest]\n'),
    ('invalid/inline-table/overwrite-implicitly.toml', 'a = { b = 1, b.c = 2 }\n'),
    ('invalid/inline-table/overwrite-value-in-inner-array.toml', 'tab = { inner.table = [{}], inner.table.val = "bad" }'),
    ('invalid/inline-table/overwrite-value-in-inner-table.toml', 'tab = { inner = { dog = "best" }, inner.cat = "worst" }'),
    ('invalid/inline-table/unclosed-empty.toml', 'a={'),
    ('invalid/invalid-comment-char.toml', '# form feed (\x0c) not allowed in comments'),
    ('invalid/invalid-escaped-unicode.toml', 'escaped-unicode = "\\uabag"\n'),
    ('invalid/invalid-hex.toml', 'hex = 0xgabba00f1\n'),
    ('invalid/keys-and-vals/ends-early-table-def.toml', '[fwfw.wafw'),
    ('invalid/keys-and-vals/ends-early.toml', 'fs.fw'),
    ('invalid/keys-and-vals/no-value.toml', 'why-no-value='),
    ('invalid/keys-and-vals/only-ws-after-dot.toml', 'fs.'),
    ('invalid/keys-and-vals/overwrite-with-deep-table.toml', 'a=1\n[a.b.c.d]\n'),
    ('invalid/literal-str/unclosed.toml', "unclosed='dwdd"),
    ('invalid/missing-closing-double-square-bracket.toml', '[[closing-bracket.missing]\nblaa=2\n'),
    ('invalid/missing-closing-square-bracket.toml', '[closing-bracket.missingö\nblaa=2\n'),
    ('invalid/multiline-basic-str/carriage-return.toml', 's="""cr is not an allowed line ending\rbut we just tried to use it\n"""'),
    ('invalid/multiline-basic-str/escape-only.toml', 'bee = """\\"""\n'),
    ('invalid/multiline-basic-str/file-ends-after-opening.toml', 'a="""'),
    ('invalid/multiline-basic-str/last-line-escape.toml', 'bee = """\nhee \\\n\ngee \\   """\n'),
    ('invalid/multiline-basic-str/unclosed-ends-in-whitespace-escape.toml', 'bee = """\nhee\ngee\\\t '),
    ('invalid/multiline-literal-str/file-ends-after-opening.toml', "a='''"),
    ('invalid/multiline-literal-str/unclosed.toml', "bee = '''\nhee\ngee ''"),
    ('invalid/non-scalar-escaped.toml', 'a="\\ud800"'),
    ('invalid/table/eof-after-opening.toml', '['),
    ('invalid/table/redefine-1.toml', '[t1]\nt2.t3.v = 0\n[t1.t2]\n'),
    ('invalid/table/redefine-2.toml', '[t1]\nt2.t3.v = 0\n[t1.t2.t3]\n'),
    ('invalid/unclosed-multiline-string.toml', 'not-closed= """\ndiibaa\nblibae ete\neteta\n'),
    ('invalid/unclosed-string.toml', '"a-string".must-be = "closed'),
    ('valid/apostrophes-in-literal-string.toml', "this-str-has-apostrophes='''' there's one already\n'' two more\n'''''\n"),
    ('valid/array/array-subtables.toml', '[[arr]]\n[arr.subtab]\nval=1\n\n[[arr]]\n[arr.subtab]\nval=2\n'),
    ('valid/array/open-parent-table.toml', '[[parent-table.arr]]\n[[parent-table.arr]]\n[parent-table]\nnot-arr = 1\n'),
    ('valid/boolean.toml', '\'a\'=true\n"b"=false'),
    ('valid/dates-and-times/datetimes.toml', 'local-dt=1988-10-27t01:01:01\nzulu-dt=1988-10-27t01:01:01z\n'),
    ('valid/dates-and-times/localtime.toml', 't=00:00:00.99999999999999'),
    ('valid/empty-inline-table.toml', 'empty ={            }#nothing here\n'),
    ('valid/five-quotes.toml', 'five-quotes = """\nClosing with five quotes\n"""""\nfour-quotes = """\nClosing with four quotes\n""""\n'),
    ('valid/hex-char.toml', 'a="\\u0061"\nb="\\u0062"\nc="\\U00000063"'),
    ('valid/multiline-basic-str/ends-in-whitespace-escape.toml', 'beee = """\nheeee\ngeeee\\  \n\n\n      """\n'),
    ('valid/no-newlines.toml', '#no newlines at all here'),
    ('valid/trailing-comma.toml', 'arr=[1,]'),
]

ok = 0
errors = 0
for name, text in DOCS:
    try:
        doc = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        errors += 1
        print(name, "TOMLDecodeError:", e)
        continue
    ok += 1
    print(name, "OK", doc)
print(ok, "valid,", errors, "invalid")
