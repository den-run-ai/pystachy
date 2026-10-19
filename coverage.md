## Hosted compiler coverage

Commit `5dcb4859d363267bb2c8ce851a4476a2b75a2c36`: 4588 passed, 0 failed (tests/run.sh, JIT and AOT, 4589 compiler processes) in 1582 s.
Lines and branches of src/pystachy_compiler/, run by CPython; not runtime.c, runtime.py or lib/.

| Name                                        |    Stmts |     Miss |   Branch |   BrPart |     Cover |
|-------------------------------------------- | -------: | -------: | -------: | -------: | --------: |
| src/pystachy\_compiler/analysis.py          |     1249 |       55 |     1076 |       49 |     94.9% |
| src/pystachy\_compiler/builtins.py          |     2054 |      104 |     1230 |       96 |     93.8% |
| src/pystachy\_compiler/calls.py             |     1101 |       77 |      676 |       48 |     92.1% |
| src/pystachy\_compiler/containers.py        |      721 |       46 |      394 |       30 |     92.5% |
| src/pystachy\_compiler/conversions.py       |      244 |        8 |      146 |        6 |     96.4% |
| src/pystachy\_compiler/declarations.py      |     2054 |      133 |     1402 |      103 |     92.6% |
| src/pystachy\_compiler/diagnostics.py       |       29 |        0 |        8 |        0 |    100.0% |
| src/pystachy\_compiler/driver.py            |      501 |      143 |      206 |       46 |     67.3% |
| src/pystachy\_compiler/emission.py          |      435 |       20 |      136 |       12 |     94.4% |
| src/pystachy\_compiler/exceptions.py        |      825 |       45 |      410 |       18 |     94.3% |
| src/pystachy\_compiler/expressions.py       |     3121 |       88 |     1836 |       90 |     96.3% |
| src/pystachy\_compiler/flow.py              |      754 |       14 |      524 |       12 |     97.7% |
| src/pystachy\_compiler/functions.py         |      277 |       59 |      158 |        4 |     76.3% |
| src/pystachy\_compiler/gen.py               |     1839 |        7 |        2 |        0 |     99.6% |
| src/pystachy\_compiler/generators.py        |      920 |       39 |      370 |       44 |     93.6% |
| src/pystachy\_compiler/ir.py                |      311 |        0 |       16 |        0 |    100.0% |
| src/pystachy\_compiler/ircheck.py           |      340 |       70 |      282 |       70 |     77.5% |
| src/pystachy\_compiler/lexer.py             |      606 |       26 |      342 |       21 |     94.6% |
| src/pystachy\_compiler/llvm\_abi.py         |       12 |        0 |        4 |        0 |    100.0% |
| src/pystachy\_compiler/loader.py            |     2374 |       76 |     1462 |       75 |     95.9% |
| src/pystachy\_compiler/local\_versions.py   |       35 |        0 |       24 |        0 |    100.0% |
| src/pystachy\_compiler/lower\_module.py     |      286 |      158 |      148 |        4 |     43.3% |
| src/pystachy\_compiler/lowering.py          |      298 |        1 |      168 |        2 |     99.4% |
| src/pystachy\_compiler/memory\_ir.py        |       17 |        0 |        0 |        0 |    100.0% |
| src/pystachy\_compiler/module.py            |       29 |        0 |        0 |        0 |    100.0% |
| src/pystachy\_compiler/names.py             |       27 |        0 |       12 |        0 |    100.0% |
| src/pystachy\_compiler/optimizations.py     |      297 |        9 |      176 |       11 |     95.8% |
| src/pystachy\_compiler/parser.py            |     1665 |       69 |      910 |       73 |     94.4% |
| src/pystachy\_compiler/program.py           |      918 |       42 |      672 |       36 |     94.5% |
| src/pystachy\_compiler/reflection.py        |     1865 |      139 |      986 |      122 |     90.3% |
| src/pystachy\_compiler/scalar\_ir.py        |       47 |        9 |       22 |        9 |     73.9% |
| src/pystachy\_compiler/scope.py             |      534 |        4 |      294 |        7 |     98.7% |
| src/pystachy\_compiler/specs.py             |      228 |        0 |       80 |        0 |    100.0% |
| src/pystachy\_compiler/statements.py        |     1556 |       63 |      848 |       61 |     94.7% |
| src/pystachy\_compiler/structs.py           |      224 |       27 |      128 |       21 |     85.8% |
| src/pystachy\_compiler/syntax.py            |      145 |        4 |       98 |        5 |     96.3% |
| src/pystachy\_compiler/templates.py         |      709 |       39 |      430 |       43 |     92.4% |
| src/pystachy\_compiler/union\_arithmetic.py |       58 |        0 |       30 |        0 |    100.0% |
| src/pystachy\_compiler/unions.py            |      320 |       12 |      166 |       12 |     95.1% |
| src/pystachy\_compiler/utils.py             |      567 |       30 |      280 |       19 |     93.3% |
| src/pystachy\_compiler/variables.py         |     1449 |       88 |      870 |       74 |     92.5% |
| **TOTAL**                                   | **31041** | **1704** | **17022** | **1223** | **93.3%** |

1 empty file skipped.
