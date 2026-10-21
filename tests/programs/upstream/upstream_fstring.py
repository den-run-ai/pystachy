# Adapted from CPython 3.13.16 Lib/test/test_fstring.py, class TestCase: test__format__lookup,
# test_literal, test_double_braces, test_compile_time_concat, test_comments,
# test_format_specifier_expressions, test_custom_format_specifier, test_side_effect_order,
# test_parens_in_expressions, test_backslashes_in_string_part,
# test_backslashes_in_expression_part, test_no_escapes_for_braces,
# test_newlines_in_expressions, test_lambda, test_valid_prefixes, test_roundtrip_raw_quotes,
# test_fstring_backslash_before_double_bracket, test_fstring_backslash_prefix_raw,
# test_fstring_format_spec_greedy_matching, test_expressions_with_triple_quoted_strings,
# test_multiple_vars, test_closure, test_arguments, test_locals, test_missing_format_spec,
# test_global, test_shadowed_global, test_call, test_nested_fstrings,
# test_leading_trailing_spaces, test_not_equal, test_equal_equal, test_conversions,
# test_if_conditional, test_empty_format_specifier, test_errors, test_loop, test_dict,
# test_debug_conversion, test_debug_expressions_are_raw_strings, test_walrus,
# test_with_two_commas_in_format_specifier and test_raw_fstring_format_spec; commit
# cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name (or several, NAME_2, ..., where its
# statements cannot share one function); its local classes are module classes. assertEqual(a,
# b) is eq(a, b), which prints a and asserts a == b; assertRaises(E, f, *args) and
# assertRaisesRegex are try statements that print the exception (the regex is not matched).
# Of a method's other statements, a function keeps the ones that bind what its assertions
# read, in upstream's order. 271 of these methods' 321 such assertions are adopted, all but
# these (test_fstring.py line numbers). test_errors' assertAllRaise(ValueError, ...) evaluates
# f'{1000:j}' twice through eval(); here each is a try statement that prints the exception.
# EXCLUDED upstream cases:
# - \N{...} escapes (rejected: "\N{...} escapes are not supported"): 972-978, 1003, 1006,
#   1033-1035, 1069; a non-ASCII identifier (rejected: "non-ASCII identifiers are not
#   supported", tenπ): 1575
# - test_str_format_differences' f-strings and str.format() of a dict with str and int keys
#   (rejected: "expected str, got int"): 1506-1510; test_format_specifier_expressions'
#   decimal.Decimal: 821-825, 831, and its `x != {...}` (rejected: "cannot compare int !=
#   dict[int,int]"): 830
# - eval() and compile() (rejected: "unsupported call eval(str)"): 1097, 1101, 1551, 1552,
#   1645; type(x).__format__ (rejected: "unsupported call type(X)"): 65, 66; 62 (an instance's
#   __format__ assigned through types.MethodType); a function's __doc__ (rejected: "type
#   <function f> has no attribute '__doc__'"): 572, 576 (test_docstring); test_missing_variable
#   (a compile-time "name 'value' is not defined", where CPython raises NameError when the code
#   runs; documented): 1231; 993, 996 (value from eval()), 1260 (unittest)
# - test_errors' assertAllRaise(TypeError, ...) snippets f'{(lambda: 0):x}' and f'{(0,):x}'
#   (compile-time errors here, with CPython's messages "unsupported format string passed to
#   function.__format__" and "... tuple.__format__", where CPython raises TypeError when the
#   code runs; documented): 1514-1517
# - test_debug_conversion's x, which upstream rebinds to a str, a float and ints and assigns
#   through := and through a closure's nonlocal: (x:="5") after x = 9 (rejected: "expected int,
#   got str"): 1600, and 1601 after it; the nonlocal-assigning f() (rejected: "f() reads 'x',
#   which may not be assigned yet where it is defined: not supported"): 1619, 1620-1622, 1658,
#   1661, 1669, 1672; 1627 (datetime.datetime.now())
# - the tests of SyntaxErrors through eval() (assertAllRaise(SyntaxError, ...)): `pystachy
#   check` reports each of their snippets as CPython does (checked with tools/syntax_sweep.py),
#   but these, whose messages differ: f'''{<U+00A0>}''' (CPython: "invalid non-printable
#   character U+00A0", Pystachy: "f-string: valid expression required before '}'"),
#   f'{1, lambda:x}' (CPython: "f-string: lambda expressions are not allowed without
#   parentheses", Pystachy: "f-string: expecting '=', or '!', or ':', or '}'"), f'' = 3,
#   del f'' and del '' f'' (CPython: "cannot assign to f-string expression here. ..." and
#   "cannot delete f-string expression", Pystachy: "... literal ...")
# - test_ast* (the ast module), test_docstring, test_literal_eval, test_many_expressions and
#   test_many_fstrings_in_module (eval(), exec()), test_yield*, test_assignment and test_del
#   (exec() of SyntaxErrors), test_debug_in_file*,
#   test_syntax_warning_infinite_recursion_in_file,
#   test_expression_in_interactive_after_buffer_resize, test_fstring_without_formatting_bytecode,
#   test_gh129093, test_newlines_in_format_specifiers (SyntaxErrors), test_gh139516 (no
#   assertion), test_filename_in_syntaxerror and the other tests that run scripts
a_global = 'global variable'


def eq(got, expected) -> None:
    print(repr(got))
    assert got == expected, (got, expected)


class X:
    def __format__(self, spec):
        return 'class'


def test__format__lookup() -> None:
    x = X()
    y = X()
    eq(f'{y}', format(y))
    eq(f'{y}', 'class')
    eq(format(x), format(y))
    eq(x.__format__(''), 'class')


def test_literal() -> None:
    eq(f'', '')
    eq(f'a', 'a')
    eq(f' ', ' ')


def test_double_braces() -> None:
    eq(f'{{', '{')
    eq(f'a{{', 'a{')
    eq(f'{{b', '{b')
    eq(f'a{{b', 'a{b')
    eq(f'}}', '}')
    eq(f'a}}', 'a}')
    eq(f'}}b', '}b')
    eq(f'a}}b', 'a}b')
    eq(f'{{}}', '{}')
    eq(f'a{{}}', 'a{}')
    eq(f'{{b}}', '{b}')
    eq(f'{{}}c', '{}c')
    eq(f'a{{b}}', 'a{b}')
    eq(f'a{{}}c', 'a{}c')
    eq(f'{{b}}c', '{b}c')
    eq(f'a{{b}}c', 'a{b}c')
    eq(f'{{{10}', '{10')
    eq(f'}}{10}', '}10')
    eq(f'}}{{{10}', '}{10')
    eq(f'}}a{{{10}', '}a{10')
    eq(f'{10}{{', '10{')
    eq(f'{10}}}', '10}')
    eq(f'{10}}}{{', '10}{')
    eq(f'{10}}}a{{' '}', '10}a{}')
    eq(f'{"{{}}"}', '{{}}')


def test_compile_time_concat() -> None:
    x = 'def'
    eq('abc' f'## {x}ghi', 'abc## defghi')
    eq('abc' f'{x}' 'ghi', 'abcdefghi')
    eq('abc' f'{x}' 'gh' f'i{x:4}', 'abcdefghidef ')
    eq('{x}' f'{x}', '{x}def')
    eq('{x' f'{x}', '{xdef')
    eq('{x}' f'{x}', '{x}def')
    eq('{{x}}' f'{x}', '{{x}}def')
    eq('{{x' f'{x}', '{{xdef')
    eq('x}}' f'{x}', 'x}}def')
    eq(f'{x}' 'x}}', 'defx}}')
    eq(f'{x}' '', 'def')
    eq('' f'{x}' '', 'def')
    eq('' f'{x}', 'def')
    eq(f'{x}' '2', 'def2')
    eq('1' f'{x}' '2', '1def2')
    eq('1' f'{x}', '1def')
    eq(f'{x}' f'-{x}', 'def-def')
    eq('' f'', '')
    eq('' f'' '', '')
    eq('' f'' '' f'', '')
    eq(f'', '')
    eq(f'' '', '')
    eq(f'' '' f'', '')
    eq(f'' '' f'' '', '')
    eq(f'{' f'}', ' f')


def test_comments() -> None:
    d = {'#': 'hash'}
    eq(f'{"#"}', '#')
    eq(f'{d["#"]}', 'hash')
    eq(f'''A complex trick: {
2  # two
}''', 'A complex trick: 2')
    eq(f'''
{
40 # forty
+  # plus
2  # two
}''', '\n42')
    eq(f'''
{
40 # forty
+  # plus
2  # two
}''', '\n42')
    eq(f'''
# this is not a comment
{ # the following operation it's
3 # this is a number
* 2}''', '\n# this is not a comment\n6')
    eq(f'''
{# f'a {comment}'
86 # constant
# nothing more
}''', '\n86')


def test_format_specifier_expressions() -> None:
    eq(f'{10:#{1}0x}', '       0xa')
    eq(f'{10:{"#"}1{0}{"x"}}', '       0xa')
    eq(f'{-10:-{"#"}1{0}x}', '      -0xa')
    eq(f'{-10:{"-"}#{1}0{"x"}}', '      -0xa')


class CustomFormat:
    def __format__(self, format_spec):
        return format_spec


def test_custom_format_specifier() -> None:
    eq(f'{CustomFormat():\n}', '\n')
    eq(f'{CustomFormat():\u2603}', '☃')


class X_side_effect_order:
    def __init__(self):
        self.i = 0
    def __format__(self, spec):
        self.i += 1
        return str(self.i)


def test_side_effect_order() -> None:
    x = X_side_effect_order()
    eq(f'{x} {x}', '1 2')


def test_parens_in_expressions() -> None:
    eq(f'{3,}', '(3,)')


def test_backslashes_in_string_part() -> None:
    eq(f'\t', '\t')
    eq(r'\t', '\\t')
    eq(rf'\t', '\\t')
    eq(f'{2}\t', '2\t')
    eq(f'{2}\t{3}', '2\t3')
    eq(f'\t{3}', '\t3')
    eq(f'\u0394', '\u0394')
    eq(r'\u0394', '\\u0394')
    eq(rf'\u0394', '\\u0394')
    eq(f'{2}\u0394', '2\u0394')
    eq(f'{2}\u0394{3}', '2\u03943')
    eq(f'\u0394{3}', '\u03943')
    eq(f'\U00000394', '\u0394')
    eq(r'\U00000394', '\\U00000394')
    eq(rf'\U00000394', '\\U00000394')
    eq(f'{2}\U00000394', '2\u0394')
    eq(f'{2}\U00000394{3}', '2\u03943')
    eq(f'\U00000394{3}', '\u03943')
    eq(f'\x20', ' ')
    eq(r'\x20', '\\x20')
    eq(rf'\x20', '\\x20')
    eq(f'{2}\x20', '2 ')
    eq(f'{2}\x20{3}', '2 3')
    eq(f'\x20{3}', ' 3')
    eq(f'2\x20', '2 ')
    eq(f'2\x203', '2 3')
    eq(f'\x203', ' 3')


def test_backslashes_in_string_part_2() -> None:
    eq(f'\\{6*7}', '\\42')
    eq(fr'\{6*7}', '\\42')
    AMPERSAND = 'spam'
    eq(f'\\N{AMPERSAND}', '\\Nspam')
    eq(fr'\N{AMPERSAND}', '\\Nspam')


def test_backslashes_in_expression_part() -> None:
    eq(f"{(
                        1 +
                        2
        )}", "3")


def test_no_escapes_for_braces() -> None:
    eq(f'\x7b1+1}}', '{1+1}')
    eq(f'\x7b1+1', '{1+1')
    eq(f'\u007b1+1', '{1+1')


def test_newlines_in_expressions() -> None:
    eq(f'{0}', '0')
    eq(rf'''{3+
4}''', '7')


def test_lambda() -> None:
    x = 5
    eq(f'{(lambda y:x*y)("8")!r}', "'88888'")
    eq(f'{(lambda y:x*y)("8")!r:10}', "'88888'   ")
    eq(f'{(lambda y:x*y)("8"):10}', "88888     ")


def test_valid_prefixes() -> None:
    eq(F'{1}', "1")
    eq(FR'{2}', "2")
    eq(fR'{3}', "3")


def test_roundtrip_raw_quotes() -> None:
    eq(fr"\'", "\\'")
    eq(fr'\"', '\\"')
    eq(fr'\"\'', '\\"\\\'')
    eq(fr'\'\"', '\\\'\\"')
    eq(fr'\"\'\"', '\\"\\\'\\"')
    eq(fr'\'\"\'', '\\\'\\"\\\'')
    eq(fr'\"\'\"\'', '\\"\\\'\\"\\\'')


def test_fstring_backslash_before_double_bracket() -> None:
    eq(fr'\{{\}}', '\\{\\}')
    eq(fr'\{{', '\\{')
    eq(fr'\{{{1+1}', '\\{2')
    eq(fr'\}}{1+1}', '\\}2')
    eq(fr'{1+1}\}}', '2\\}')


def test_fstring_backslash_prefix_raw() -> None:
    eq(f'\\', '\\')
    eq(f'\\\\', '\\\\')
    eq(fr'\\', r'\\')
    eq(fr'\\\\', r'\\\\')
    eq(rf'\\', r'\\')
    eq(rf'\\\\', r'\\\\')
    eq(Rf'\\', R'\\')
    eq(Rf'\\\\', R'\\\\')
    eq(fR'\\', R'\\')
    eq(fR'\\\\', R'\\\\')
    eq(FR'\\', R'\\')
    eq(FR'\\\\', R'\\\\')


def test_fstring_format_spec_greedy_matching() -> None:
    eq(f"{1:}}}", "1}")
    eq(f"{1:>3{5}}}}", "                                  1}")


def test_expressions_with_triple_quoted_strings() -> None:
    eq(f"{'''x'''}", 'x')
    eq(f"{'''eric's'''}", "eric's")
    eq(f'{"x" """eric"s""" "y"}', 'xeric"sy')
    eq(f'{"x" """eric"s"""}', 'xeric"s')
    eq(f'{"""eric"s""" "y"}', 'eric"sy')
    eq(f'{"""x""" """eric"s""" "y"}', 'xeric"sy')
    eq(f'{"""x""" """eric"s""" """y"""}', 'xeric"sy')
    eq(f'{r"""x""" """eric"s""" """y"""}', 'xeric"sy')


def test_multiple_vars() -> None:
    x = 98
    y = 'abc'
    eq(f'{x}{y}', '98abc')
    eq(f'X{x}{y}', 'X98abc')
    eq(f'{x}X{y}', '98Xabc')
    eq(f'{x}{y}X', '98abcX')
    eq(f'X{x}Y{y}', 'X98Yabc')
    eq(f'X{x}{y}Y', 'X98abcY')
    eq(f'{x}X{y}Y', '98XabcY')
    eq(f'X{x}Y{y}Z', 'X98YabcZ')


def test_closure() -> None:
    def outer(x):
        def inner():
            return f'x:{x}'
        return inner
    eq(outer('987')(), 'x:987')
    eq(outer(7)(), 'x:7')


def test_arguments() -> None:
    y = 2
    def f(x, width):
        return f'x={x*y:{width}}'
    eq(f('foo', 10), 'x=foofoo    ')
    x = 'bar'
    eq(f(10, 10), 'x=        20')


def test_locals() -> None:
    value = 123
    eq(f'v:{value}', 'v:123')


class O:
    def __format__(self, spec):
        if not spec:
            return '*'
        return spec


def test_missing_format_spec() -> None:
    eq(f'{O():x}', 'x')
    eq(f'{O()}', '*')
    eq(f'{O():}', '*')
    eq(f'{3:}', '3')
    eq(f'{3!s:}', '3')


def test_global() -> None:
    eq(f'g:{a_global}', 'g:global variable')
    eq(f'g:{a_global!r}', "g:'global variable'")
    a_local = 'local variable'
    eq(f'g:{a_global} l:{a_local}', 'g:global variable l:local variable')
    eq(f'g:{a_global!r}', "g:'global variable'")
    eq(f'g:{a_global} l:{a_local!r}', "g:global variable l:'local variable'")


def test_shadowed_global() -> None:
    a_global = 'really a local'
    eq(f'g:{a_global}', 'g:really a local')
    eq(f'g:{a_global!r}', "g:'really a local'")
    a_local = 'local variable'
    eq(f'g:{a_global} l:{a_local}', 'g:really a local l:local variable')
    eq(f'g:{a_global!r}', "g:'really a local'")
    eq(f'g:{a_global} l:{a_local!r}', "g:really a local l:'local variable'")


def test_call() -> None:
    def foo(x):
        return 'x=' + str(x)
    eq(f'{foo(10)}', 'x=10')


def test_nested_fstrings() -> None:
    y = 5
    eq(f'{f"{0}"*3}', '000')
    eq(f'{f"{y}"*3}', '555')


def test_leading_trailing_spaces() -> None:
    eq(f'{ 3}', '3')
    eq(f'{  3}', '3')
    eq(f'{3 }', '3')
    eq(f'{3  }', '3')
    eq(f'expr={ {x: y for x, y in [(1, 2), ]}}', 'expr={1: 2}')
    eq(f'expr={ {x: y for x, y in [(1, 2), ]} }', 'expr={1: 2}')


def test_not_equal() -> None:
    eq(f'{3!=4}', 'True')
    eq(f'{3!=4:}', 'True')
    eq(f'{3!=4!s}', 'True')
    eq(f'{3!=4!s:.3}', 'Tru')
    a = 3
    b = 4
    eq(f'{a!=b=:>10}', 'a!=b=         1')


def test_equal_equal() -> None:
    eq(f'{0==1}', 'False')


def test_conversions() -> None:
    eq(f'{3.14:10.10}', '      3.14')
    eq(f'{1.25!s:10.10}', '1.25      ')
    eq(f'{1.25!r:10.10}', '1.25      ')
    eq(f'{1.25!a:10.10}', '1.25      ')
    eq(f'{"a"}', 'a')
    eq(f'{"a"!r}', "'a'")
    eq(f'{"a"!a}', "'a'")
    eq(f"{3!s  }", "3")
    eq(f'{1.25!s  :10.10}', '1.25      ')
    eq(f'{"a!r"}', "a!r")
    eq(f'{3.14:!<10.10}', '3.14!!!!!!')


def test_if_conditional() -> None:
    def test_fstring(x, expected):
        flag = 0
        if f'{x}':
            flag = 1
        else:
            flag = 2
        self.assertEqual(flag, expected)
    def test_concat_empty(x, expected):
        flag = 0
        if '' f'{x}':
            flag = 1
        else:
            flag = 2
        self.assertEqual(flag, expected)
    def test_concat_non_empty(x, expected):
        flag = 0
        if ' ' f'{x}':
            flag = 1
        else:
            flag = 2
        self.assertEqual(flag, expected)


def test_empty_format_specifier() -> None:
    x = 'test'
    eq(f'{x}', 'test')
    eq(f'{x:}', 'test')
    eq(f'{x!s:}', 'test')
    eq(f'{x!r:}', "'test'")


def test_errors() -> None:
    try:
        f'{1000:j}'
    except ValueError as e:
        print(type(e).__name__ + ':', e)
    try:
        f'{1000:j}'
    except ValueError as e:
        print(type(e).__name__ + ':', e)


def test_loop() -> None:
    for i in range(1000):
        eq(f'i:{i}', 'i:' + str(i))


def test_dict() -> None:
    d = {'"': 'dquote',
         "'": 'squote',
         'foo': 'bar',
         }
    eq(f'''{d["'"]}''', 'squote')
    eq(f"""{d['"']}""", 'dquote')
    eq(f'{d["foo"]}', 'bar')
    eq(f"{d['foo']}", 'bar')


def test_debug_conversion() -> None:
    x = 'A string'
    eq(f'{x=}', 'x=' + repr(x))
    eq(f'{x =}', 'x =' + repr(x))
    eq(f'{x=!s}', 'x=' + str(x))
    eq(f'{x=!r}', 'x=' + repr(x))
    eq(f'{x=!a}', 'x=' + ascii(x))
    x = 2.71828
    eq(f'{x=:.2f}', 'x=' + format(x, '.2f'))
    eq(f'{x=:}', 'x=' + format(x, ''))
    eq(f'{x=!r:^20}', 'x=' + format(repr(x), '^20'))
    eq(f'{x=!s:^20}', 'x=' + format(str(x), '^20'))
    eq(f'{x=!a:^20}', 'x=' + format(ascii(x), '^20'))
    x = 9
    eq(f'{3*x+15=}', '3*x+15=42')
    eq(f'{"Σ"=}', '"Σ"=\'Σ\'')
    eq(f'{f"{3.1415=:.1f}":*^20}', '*****3.1415=3.1*****')
    pi = 'π'
    eq(f'alpha α {pi=} ω omega', "alpha α pi='π' ω omega")
    eq(f'''{
3
=}''', '\n3\n=3')
    eq(f'{0==1}', 'False')
    eq(f'{0!=1}', 'True')
    eq(f'{0<=1}', 'True')
    eq(f'{0>=1}', 'False')


def test_debug_conversion_2() -> None:
    eq(f'{(x:="5")}', '5')


def test_debug_conversion_3() -> None:
    x = 9
    eq(f'{(x:=5)}', '5')
    eq(x, 5)
    eq(f'{"="}', '=')
    x = 20
    eq(f'{x:=10}', '        20')


def test_debug_conversion_4() -> None:
    y = 20
    eq(f"{2:{y=}}", "yyyyyyyyyyyyyyyyyyy2")


class C:
    def __format__(self, s):
        return f'FORMAT-{s}'
    def __repr__(self):
        return 'REPR'


def test_debug_conversion_5() -> None:
    eq(f'{C()=}', 'C()=REPR')
    eq(f'{C()=!r}', 'C()=REPR')
    eq(f'{C()=:}', 'C()=FORMAT-')
    eq(f'{C()=: }', 'C()=FORMAT- ')
    eq(f'{C()=:x}', 'C()=FORMAT-x')
    eq(f'{C()=!r:*^20}', 'C()=********REPR********')
    eq(f"{C():{20=}}", 'FORMAT-20=20')
    x = 'foo'
    eq(f'X{x=}Y', 'Xx='+repr(x)+'Y')
    eq(f'X{x  =}Y', 'Xx  ='+repr(x)+'Y')
    eq(f'X{x=  }Y', 'Xx=  '+repr(x)+'Y')
    eq(f'X{x  =  }Y', 'Xx  =  '+repr(x)+'Y')
    eq(f"sadsd {1 + 1 =  :{1 + 1:1d}f}", "sadsd 1 + 1 =  2.000000")
    eq(f'{" # nooo "=}', '" # nooo "=\' # nooo \'')
    eq(f'{" \" # nooo \" "=}', '" \\" # nooo \\" "=\' " # nooo " \'')
    eq(f'{"""# this is not a comment
        a""" # this is a comment
        }', '# this is not a comment\n        a')


def test_debug_expressions_are_raw_strings() -> None:
    eq(f'{r"\xff"=}', 'r"\\xff"=\'\\\\xff\'')
    eq(f'{r"\n"=}', 'r"\\n"=\'\\\\n\'')
    eq(f"{'\''=}", "'\\''=\"'\"")
    eq(f'{'\xc5'=}', r"'\xc5'='Å'")


def test_walrus() -> None:
    x = 20
    eq(f'{x:=10}', '        20')
    eq(f'{(x:=10)}', '10')
    eq(x, 10)


def test_with_two_commas_in_format_specifier() -> None:
    try:
        f'{1:,,}'
    except ValueError as e:
        print(type(e).__name__ + ':', e)


class UnchangedFormat:
    """Test helper that returns the format spec unchanged."""
    def __format__(self, format):
        return format


def test_raw_fstring_format_spec() -> None:
    eq(f"{UnchangedFormat():\xFF}", 'ÿ')
    eq(rf"{UnchangedFormat():\xFF}", '\\xFF')
    eq(rf"{UnchangedFormat():{'\xFF'}}", 'ÿ')
    eq(f"{UnchangedFormat():{r'\xFF'}}", '\\xFF')
    eq(rf"{UnchangedFormat():{r'\xFF'}}", '\\xFF')
    eq(f"""{UnchangedFormat():{'a'\
                        'b'}}""", 'ab')
    eq(rf"""{UnchangedFormat():{'a'\
                         'b'}}""", 'ab')
    eq(rf"{UnchangedFormat():\xFF} {UnchangedFormat():\n}", '\\xFF \\n')


test__format__lookup()
test_literal()
test_double_braces()
test_compile_time_concat()
test_comments()
test_format_specifier_expressions()
test_custom_format_specifier()
test_side_effect_order()
test_parens_in_expressions()
test_backslashes_in_string_part()
test_backslashes_in_string_part_2()
test_backslashes_in_expression_part()
test_no_escapes_for_braces()
test_newlines_in_expressions()
test_lambda()
test_valid_prefixes()
test_roundtrip_raw_quotes()
test_fstring_backslash_before_double_bracket()
test_fstring_backslash_prefix_raw()
test_fstring_format_spec_greedy_matching()
test_expressions_with_triple_quoted_strings()
test_multiple_vars()
test_closure()
test_arguments()
test_locals()
test_missing_format_spec()
test_global()
test_shadowed_global()
test_call()
test_nested_fstrings()
test_leading_trailing_spaces()
test_not_equal()
test_equal_equal()
test_conversions()
test_if_conditional()
test_empty_format_specifier()
test_errors()
test_loop()
test_dict()
test_debug_conversion()
test_debug_conversion_2()
test_debug_conversion_3()
test_debug_conversion_4()
test_debug_conversion_5()
test_debug_expressions_are_raw_strings()
test_walrus()
test_with_two_commas_in_format_specifier()
test_raw_fstring_format_spec()
