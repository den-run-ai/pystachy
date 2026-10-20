# Adapted from CPython 3.13.16 Lib/test/test_re.py, commit cbc944f4bc59639a444dd971c737788ba2283a91:
# the errors that ReTests checks (checkPatternError, checkTemplateError and the assertRaises of
# test_basic_re_sub, test_sub_template_numeric_escape, test_symbolic_groups_errors,
# test_symbolic_refs_errors, test_re_groupref_exists_errors, test_re_groupref_overflow,
# test_re_groupref, test_repeat_minmax, test_other_escapes, test_named_unicode_escapes,
# test_lookbehind, test_sre_character_literals, test_sre_character_class_literals,
# test_character_set_errors, test_nothing_to_repeat, test_multiple_repeat, test_inline_flags,
# test_ascii_and_unicode_flag, test_locale_flag, test_scoped_flags, test_repeat_minmax_overflow,
# test_look_behind_overflow, test_backref_group_name_in_exception, test_group_name_in_exception,
# test_error, test_misc_errors, test_bug_1661, test_compile, test_group, test_match_getitem).
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
#
# Each case runs through lib/re, Pystachy's port of re, compiled; this file's .out was recorded
# with CPython's own re. The unittest scaffolding becomes tables of the upstream arguments and
# expected values: each case prints the exception (its message and position) and asserts what
# upstream asserts. A position in a pattern with non-ASCII characters prints as the pattern's text
# before it, and is not compared with upstream's number: Pystachy's positions count UTF-8 bytes
# there (lib/README.md, a documented deviation).
#
# EXCLUDED (not in the tables):
# - bytes patterns and templates (test_symbolic_groups_errors' and test_symbolic_refs_errors'
#   b'\xc2\xb5' cases, test_named_unicode_escapes' br'\N{...}', the test_sre_byte_*literals
#   errors, test_inline_flags' b'A(?i)', test_scoped_flags' br'(?aL:a)', and the bytes
#   incompatibilities of test_ascii_and_unicode_flag and test_locale_flag): str patterns only.
# - test_named_unicode_escapes' "undefined character name" cases (\N{SPAM}, [\N{SNAKE]}, ...): the
#   port has no table of character names, so a well-formed \N{...} is its own error (a documented
#   deviation, tests/deviations/lib_re.py); its malformed \N cases are here.
# - test_misuse_flags and the positional count/maxsplit/flags of test_qualified_re_sub,
#   test_re_subn and test_qualified_re_split: CPython's DeprecationWarning (the port has no
#   warnings) and TypeErrors of argument counts that Pystachy rejects when it compiles.
# - test_bug_40736 (re.search("x*", 5)) and test_bytes_str_mixing: a str parameter given an int or
#   bytes is a compile-time error in Pystachy.
# - test_group's m.group(1<<1000) and Index objects (__index__), test_match_getitem's format_map(),
#   assignment and len(): 64-bit ints, and the port's Match has no __index__ groups (lib/README.md).
# - test_error_is_PatternError_alias: re.error is the base class of re.PatternError in the port (a
#   documented deviation).
# - test_error's bytes pattern b'(\xa4))'.
import re


def at(s: str, i: int | None) -> str:
    # a position in s: the index, or in non-ASCII text the text before it (Pystachy's index counts
    # UTF-8 bytes there, a documented deviation, but slices out the same text)
    if i is None:
        return "None"
    if i < 0 or s.isascii():
        return str(i)
    return repr(s[:i])


def describe(s: str, e: re.error) -> str:
    # the error as str() shows it (message, position, line and column), but in non-ASCII text
    if s.isascii():
        return str(e)
    return "%s at %s" % (e.msg, at(s, e.pos))


def check_pattern(pattern: str, errmsg: str, pos: int, flags: int = 0) -> None:
    # checkPatternError: compiling the pattern raises re.PatternError with this msg (and this pos
    # where it is not -1)
    try:
        re.compile(pattern, flags)
    except re.error as e:
        print("compile", repr(pattern), "->", describe(pattern, e))
        assert e.msg == errmsg, e.msg
        assert e.pattern == pattern
        assert pos < 0 or not pattern.isascii() or e.pos == pos, str(e.pos)
        return
    raise AssertionError("no error: %r" % pattern)


def check_template(pattern: str, repl: str, string: str, errmsg: str, pos: int) -> None:
    # checkTemplateError: re.sub() of the replacement raises re.PatternError, positioned in it
    try:
        re.sub(pattern, repl, string)
    except re.error as e:
        print("sub", repr(pattern), repr(repl), repr(string), "->", describe(repl, e))
        assert e.msg == errmsg, e.msg
        assert pos < 0 or not repl.isascii() or e.pos == pos, str(e.pos)
        return
    raise AssertionError("no error: %r" % repl)


def raises(pattern: str, flags: int = 0) -> None:
    # assertRaises(re.PatternError, re.compile, ...), or the ValueError or OverflowError of a
    # compile: the exception and its message
    try:
        re.compile(pattern, flags)
    except re.error as e:
        print("compile", repr(pattern), int(flags), "->", describe(pattern, e))
        return
    except OverflowError as e:
        print("compile", repr(pattern), int(flags), "-> OverflowError:", e)
        return
    except ValueError as e:
        print("compile", repr(pattern), int(flags), "-> ValueError:", e)
        return
    raise AssertionError("no error: %r" % pattern)


# test_sub_template_numeric_escape
TEMPLATES = [
    ('x', r'\400', 'x', r'octal escape value \400 outside of range 0-0o377', 0),
    ('x', r'\777', 'x', r'octal escape value \777 outside of range 0-0o377', 0),
    ('x', r'\1', 'x', 'invalid group reference 1', 1),
    ('x', r'\8', 'x', 'invalid group reference 8', 1),
    ('x', r'\9', 'x', 'invalid group reference 9', 1),
    ('x', r'\11', 'x', 'invalid group reference 11', 1),
    ('x', r'\18', 'x', 'invalid group reference 18', 1),
    ('x', r'\1a', 'x', 'invalid group reference 1', 1),
    ('x', r'\90', 'x', 'invalid group reference 90', 1),
    ('x', r'\99', 'x', 'invalid group reference 99', 1),
    ('x', r'\118', 'x', 'invalid group reference 11', 1),
    ('x', r'\11a', 'x', 'invalid group reference 11', 1),
    ('x', r'\181', 'x', 'invalid group reference 18', 1),
    ('x', r'\800', 'x', 'invalid group reference 80', 1),
    ('x', r'\8', '', 'invalid group reference 8', 1),
    # test_symbolic_refs_errors
    ('(?P<a>x)', r'\g<a', 'xx', 'missing >, unterminated name', 3),
    ('(?P<a>x)', r'\g<', 'xx', 'missing group name', 3),
    ('(?P<a>x)', r'\g', 'xx', 'missing <', 2),
    ('(?P<a>x)', r'\g<a a>', 'xx', "bad character in group name 'a a'", 3),
    ('(?P<a>x)', r'\g<>', 'xx', 'missing group name', 3),
    ('(?P<a>x)', r'\g<1a1>', 'xx', "bad character in group name '1a1'", 3),
    ('(?P<a>x)', r'\g<2>', 'xx', 'invalid group reference 2', 3),
    ('(?P<a>x)', r'\2', 'xx', 'invalid group reference 2', 1),
    ('(?P<a>x)', r'\g<-1>', 'xx', "bad character in group name '-1'", 3),
    ('(?P<a>x)', r'\g<+1>', 'xx', "bad character in group name '+1'", 3),
    ('()' * 10, r'\g<1_0>', 'xx', "bad character in group name '1_0'", 3),
    ('(?P<a>x)', r'\g< 1 >', 'xx', "bad character in group name ' 1 '", 3),
    ('(?P<a>x)', r'\g<©>', 'xx', "bad character in group name '©'", 3),
    ('(?P<a>x)', r'\g<㊀>', 'xx', "bad character in group name '㊀'", 3),
    ('(?P<a>x)', r'\g<¹>', 'xx', "bad character in group name '¹'", 3),
    ('(?P<a>x)', r'\g<१>', 'xx', "bad character in group name '१'", 3),
    # test_re_groupref_overflow (MAXGROUPS = 2**30 - 1 on a 64-bit build)
    ('()', r'\g<1073741823>', 'xx', 'invalid group reference 1073741823', 3),
]
for pattern, repl, string, errmsg, pos in TEMPLATES:
    check_template(pattern, repl, string, errmsg, pos)

# test_symbolic_refs_errors: a group name the pattern lacks is an IndexError
try:
    re.sub('(?P<a>x)', r'\g<ab>', 'xx')
except IndexError as e:
    print("sub '(?P<a>x)' '\\\\g<ab>' -> IndexError:", e)

# test_basic_re_sub: an unknown ASCII letter escape in a replacement
for c in 'cdehijklmopqsuwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ':
    try:
        re.sub('a', '\\' + c, 'a')
        print("no error:", c)
    except re.error as e:
        print("sub 'a'", repr('\\' + c), "->", e)

PATTERNS = [
    # test_symbolic_groups_errors
    (r'(?P<a>)(?P<a>)', "redefinition of group name 'a' as group 2; was group 1", -1),
    (r'(?P<a>(?P=a))', "cannot refer to an open group", 10),
    (r'(?Pxy)', 'unknown extension ?Px', -1),
    (r'(?P<a>)(?P=a', 'missing ), unterminated name', 11),
    (r'(?P=', 'missing group name', 4),
    (r'(?P=)', 'missing group name', 4),
    (r'(?P=1)', "bad character in group name '1'", 4),
    (r'(?P=a)', "unknown group name 'a'", -1),
    (r'(?P=a1)', "unknown group name 'a1'", -1),
    (r'(?P=a.)', "bad character in group name 'a.'", 4),
    (r'(?P<)', 'missing >, unterminated name', 4),
    (r'(?P<a', 'missing >, unterminated name', 4),
    (r'(?P<', 'missing group name', 4),
    (r'(?P<>)', 'missing group name', 4),
    (r'(?P<1>)', "bad character in group name '1'", 4),
    (r'(?P<a.>)', "bad character in group name 'a.'", 4),
    (r'(?(', 'missing group name', 3),
    (r'(?())', 'missing group name', 3),
    (r'(?(a))', "unknown group name 'a'", 3),
    (r'(?(-1))', "bad character in group name '-1'", 3),
    (r'(?(1a))', "bad character in group name '1a'", 3),
    (r'(?(a.))', "bad character in group name 'a.'", 3),
    ('(?P<©>x)', "bad character in group name '©'", 4),
    ('(?P=©)', "bad character in group name '©'", 4),
    ('(?(©)y)', "bad character in group name '©'", 3),
    # test_re_groupref_exists_errors
    (r'(?P<a>)(?(0)a|b)', 'bad group number', 10),
    (r'()(?(-1)a|b)', "bad character in group name '-1'", 5),
    (r'()(?(+1)a|b)', "bad character in group name '+1'", 5),
    (r'()' * 10 + r'(?(1_0)a|b)', "bad character in group name '1_0'", 23),
    (r'()(?( 1 )a|b)', "bad character in group name ' 1 '", 5),
    (r'()(?(㊀)a|b)', "bad character in group name '㊀'", 5),
    (r'()(?(¹)a|b)', "bad character in group name '¹'", 5),
    (r'()(?(१)a|b)', "bad character in group name '१'", 5),
    (r'()(?(1', "missing ), unterminated name", 5),
    (r'()(?(1)a', "missing ), unterminated subpattern", 2),
    (r'()(?(1)a|b', 'missing ), unterminated subpattern', 2),
    (r'()(?(1)a|b|c', 'conditional backref with more than two branches', 10),
    (r'()(?(1)a|b|c)', 'conditional backref with more than two branches', 10),
    (r'()(?(2)a)', "invalid group reference 2", 5),
    # test_re_groupref_overflow
    (r'(?P<a>)(?(1073741823))', 'invalid group reference 1073741823', 10),
    # test_re_groupref
    (r'(abc\1)', 'cannot refer to an open group', 4),
    # test_repeat_minmax
    (r'x{2,1}', 'min repeat greater than max repeat', 2),
    # test_other_escapes
    ("\\", 'bad escape (end of pattern)', 0),
    # test_named_unicode_escapes (the malformed ones)
    (r'\N', 'missing {', 2),
    (r'[\N]', 'missing {', 3),
    (r'\N{', 'missing character name', 3),
    (r'[\N{', 'missing character name', 4),
    (r'\N{}', 'missing character name', 3),
    (r'[\N{}]', 'missing character name', 4),
    (r'\NSNAKE}', 'missing {', 2),
    (r'[\NSNAKE}]', 'missing {', 3),
    (r'\N{SNAKE', 'missing }, unterminated name', 3),
    (r'[\N{SNAKE]', 'missing }, unterminated name', 4),
    # test_sre_character_literals
    (r"\567", r'octal escape value \567 outside of range 0-0o377', 0),
    (r"\911", 'invalid group reference 91', 1),
    (r"\x1", r'incomplete escape \x1', 0),
    (r"\x1z", r'incomplete escape \x1', 0),
    (r"\u123", r'incomplete escape \u123', 0),
    (r"\u123z", r'incomplete escape \u123', 0),
    (r"\U0001234", r'incomplete escape \U0001234', 0),
    (r"\U0001234z", r'incomplete escape \U0001234', 0),
    (r"\U00110000", r'bad escape \U00110000', 0),
    # test_sre_character_class_literals
    (r"[\567]", r'octal escape value \567 outside of range 0-0o377', 1),
    (r"[\911]", r'bad escape \9', 1),
    (r"[\x1z]", r'incomplete escape \x1', 1),
    (r"[\u123z]", r'incomplete escape \u123', 1),
    (r"[\U0001234z]", r'incomplete escape \U0001234', 1),
    (r"[\U00110000]", r'bad escape \U00110000', 1),
    # test_character_set_errors
    (r'[', 'unterminated character set', 0),
    (r'[^', 'unterminated character set', 0),
    (r'[a', 'unterminated character set', 0),
    (r"[a-", 'unterminated character set', 0),
    (r"[\w-b]", r'bad character range \w-b', 1),
    (r"[a-\w]", r'bad character range a-\w', 1),
    (r"[b-a]", 'bad character range b-a', 1),
    # test_inline_flags (upper_char is '\u1ea0', LATIN CAPITAL LETTER A WITH DOT BELOW)
    ('\u1ea0(?i)', "global flags not at the start of the expression", 1),
    ('(?s).(?i)\u1ea0', "global flags not at the start of the expression", 5),
    ('(?i) \u1ea0 (?x)', "global flags not at the start of the expression", 7),
    (' (?x) (?i) \u1ea0', "global flags not at the start of the expression", 1),
    ('^(?i)\u1ea0', "global flags not at the start of the expression", 1),
    ('$|(?i)\u1ea0', "global flags not at the start of the expression", 2),
    ('(?:(?i)\u1ea0)', "global flags not at the start of the expression", 3),
    ('(^)?(?(1)(?i)\u1ea0)', "global flags not at the start of the expression", 9),
    ('($)?(?(1)|(?i)\u1ea0)', "global flags not at the start of the expression", 10),
    # test_scoped_flags
    (r'(?a)(?-a:\w)', "bad inline flags: cannot turn off flags 'a', 'u' and 'L'", 8),
    (r'(?i-i:a)', 'bad inline flags: flag turned on and off', 5),
    (r'(?au:a)', "bad inline flags: flags 'a', 'u' and 'L' are incompatible", 4),
    (r'(?-', 'missing flag', 3),
    (r'(?-+', 'missing flag', 3),
    (r'(?-z', 'unknown flag', 3),
    (r'(?-i', 'missing :', 4),
    (r'(?-i)', 'missing :', 4),
    (r'(?-i+', 'missing :', 4),
    (r'(?-iz', 'unknown flag', 4),
    (r'(?i:', 'missing ), unterminated subpattern', 0),
    (r'(?i', 'missing -, : or )', 3),
    (r'(?i+', 'missing -, : or )', 3),
    (r'(?iz', 'unknown flag', 3),
    # test_backref_group_name_in_exception, test_group_name_in_exception
    ('(?P=<foo>)', "bad character in group name '<foo>'", 4),
    ('(?P<?foo>)', "bad character in group name '?foo'", 4),
    # test_misc_errors
    (r'(', 'missing ), unterminated subpattern', 0),
    (r'((a|b)', 'missing ), unterminated subpattern', 0),
    (r'(a|b))', 'unbalanced parenthesis', 5),
    (r'(?P', 'unexpected end of pattern', 3),
    (r'(?z)', 'unknown extension ?z', 1),
    (r'(?iz)', 'unknown flag', 3),
    (r'(?i', 'missing -, : or )', 3),
    (r'(?#abc', 'missing ), unterminated comment', 0),
    (r'(?<', 'unexpected end of pattern', 3),
    (r'(?<>)', 'unknown extension ?<>', 1),
    (r'(?', 'unexpected end of pattern', 2),
]
for pattern, errmsg, pos in PATTERNS:
    check_pattern(pattern, errmsg, pos)

# test_nothing_to_repeat
for reps in '*', '+', '?', '{1,2}':
    for mod in '', '?':
        check_pattern('%s%s' % (reps, mod), 'nothing to repeat', 0)
        check_pattern('(?:%s%s)' % (reps, mod), 'nothing to repeat', 3)

# test_multiple_repeat
for outer_reps in '*', '+', '?', '{1,2}':
    for outer_mod in '', '?', '+':
        outer_op = outer_reps + outer_mod
        for inner_reps in '*', '+', '?', '{1,2}':
            for inner_mod in '', '?', '+':
                if inner_mod + outer_reps in ('?', '+'):
                    continue
                inner_op = inner_reps + inner_mod
                check_pattern(r'x%s%s' % (inner_op, outer_op), 'multiple repeat', 1 + len(inner_op))

# test_other_escapes: unknown ASCII letter escapes, outside and inside a class
for c in 'ceghijklmopqyzCEFGHIJKLMNOPQRTVXY':
    raises('\\%c' % c)
for c in 'ceghijklmopqyzABCEFGHIJKLMNOPQRTVXYZ':
    raises('[\\%c]' % c)

# test_lookbehind: groups referred to before they are defined, or defined inside the lookbehind
for pattern in [r'(a)b(?<=(?(2)b|x))(c)', r'(a)b(?<=(.)\2)(c)', r'(a)b(?<=(?P<a>.)(?P=a))(c)',
                r'(a)b(?<=(a)(?(2)b|x))(c)', r'(a)b(?<=(.)(?<=\2))(c)']:
    raises(pattern)

# test_ascii_and_unicode_flag and test_locale_flag: incompatible flags
raises(r'\w', re.UNICODE | re.ASCII)
raises(r'(?u)\w', re.ASCII)
raises(r'(?a)\w', re.UNICODE)
raises(r'(?au)\w')
raises('', re.LOCALE)
raises('(?L)')

# test_repeat_minmax_overflow: 2**128 and 2**129 as repeat counts
raises(r".{340282366920938463463374607431768211456}")
raises(r".{,340282366920938463463374607431768211456}")
raises(r".{340282366920938463463374607431768211456,}?")
raises(r".{680564733841876926926749214863536422912,340282366920938463463374607431768211456}")

# test_look_behind_overflow: a lookbehind 2**66 characters wide (2**22 three times over)
raises(r"(?<=((.{4194304}){4194304}){4194304})")
raises(r"(?<!((.{4194304}){4194304}){4194304})")

# test_error: the error's pattern, pos, lineno and colno, in one line and in several
try:
    re.compile('(\u20ac))')
except re.error as e:
    pat = e.pattern
    assert pat is not None and pat == '(\u20ac))'
    assert e.lineno == 1
    assert e.msg in str(e)
    print("compile '(\u20ac))' ->", repr(e.msg), at('(\u20ac))', e.pos), e.lineno)
try:
    re.compile("""
                (
                    abc
                )
                )
                (
                """, re.VERBOSE)
except re.error as e:
    assert e.pos == 77 and e.lineno == 5 and e.colno == 17
    assert e.msg in str(e) and ' at position 77' in str(e) and '(line 5, column 17)' in str(e)
    print("compile VERBOSE ->", repr(str(e)), e.msg, e.pos, e.lineno, e.colno)

# test_bug_1661: flags with a compiled pattern
pattern1 = re.compile('.')
for name in ["match", "search", "findall", "compile"]:
    try:
        if name == "match":
            re.match(pattern1, 'A', re.I)
        elif name == "search":
            re.search(pattern1, 'A', re.I)
        elif name == "findall":
            re.findall(pattern1, 'A', re.I)
        else:
            re.compile(pattern1, re.I)
        print(name, "no error")
    except ValueError as e:
        print(name, "ValueError:", e)

# test_compile: neither a str nor a pattern
try:
    re.compile(0)
except TypeError as e:
    print("compile(0) TypeError:", e)

# test_group, test_match_getitem: groups that do not exist
m = re.match('(a)(b)', 'ab')
assert m is not None
for g in [-1, 3]:
    try:
        print(m.group(g))
    except IndexError as e:
        print("group", g, "IndexError:", e)
try:
    print(m.group('x'))
except IndexError as e:
    print("group 'x' IndexError:", e)
m2 = re.compile('(?:(?P<a1>a)|(?P<b2>b))(?P<c3>c)?').match('a')
assert m2 is not None
for k in [-1, 4]:
    try:
        print(m2[k])
    except IndexError as e:
        print("m[%d] IndexError:" % k, e)
try:
    print(m2['X'])
except IndexError as e:
    print("m['X'] IndexError:", e)
try:
    print(m2[0, 1])
except IndexError as e:
    print("m[0, 1] IndexError:", e)
