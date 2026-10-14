# Additional port regressions: the complete named-entity table, Unicode tails,
# code-point bounds and decimal digit-limit errors. These are not additional
# complete upstream test methods.
import html
from html.entities import codepoint2name, entitydefs, html5, name2codepoint

for name, char in html5.items():
    assert html.unescape('&'+name) == char, name
    assert html.unescape('&'+name+'é中😀') == char+'é中😀', name
print('html5 named references:', len(html5))

for name, cp in name2codepoint.items():
    assert entitydefs[name] == '%c' % cp, name
    # HTML4 intentionally retains U+2329/U+232A for lang/rang; HTML5 uses
    # U+27E8/U+27E9. All other HTML4 names agree with the literal HTML5 table.
    if name == 'lang':
        assert entitydefs[name] == '\u2329'
    elif name == 'rang':
        assert entitydefs[name] == '\u232a'
    else:
        assert entitydefs[name] == html5[name+';'], name
    assert name2codepoint[codepoint2name[cp]] == cp, name
print('HTML4 entity mappings:', len(name2codepoint))

# A Unicode scalar below 256 must be encoded as UTF-8, not chr()'s raw byte.
assert html.unescape('&#233;') == 'é'
for cp in range(128, 256):
    expected = '%c' % cp
    if cp in html._invalid_charrefs:
        expected = html._invalid_charrefs[cp]
    elif cp in html._invalid_codepoints:
        expected = ''
    assert html.unescape('&#%d;' % cp) == expected
    assert html.unescape('&#x%x;' % cp) == expected

assert html.escape('é中😀<>&"\'\x00') == 'é中😀&lt;&gt;&amp;&quot;&#x27;\x00'
assert html.escape('é中😀<>&"\'\x00', False) == 'é中😀&lt;&gt;&amp;"\'\x00'
for text in ['&#9223372036854775808;', '&#999999999999999999999999;',
             '&#xFFFFFFFFFFFFFFFFFFFFFFFF;', '&#x'+'f'*5000+';']:
    assert html.unescape(text) == '\uFFFD'
for text in ['&#'+'0'*4300+';', '&#x'+'0'*5000+';']:
    assert html.unescape(text) == '\uFFFD'
assert html.unescape('&#'+'0'*4200+'65;') == 'A'
assert html.unescape('&#x'+'0'*5000+'41;') == 'A'
assert html.unescape('&#1114111;') == ''
assert html.unescape('&#1114112;') == '\uFFFD'
assert html.unescape('&#x10ffff;') == ''
assert html.unescape('&#x110000;') == '\uFFFD'
for digit in ['0', '9']:
    failed = False
    try:
        html.unescape('&#'+digit*4301+';')
    except ValueError as error:
        assert str(error) == (
            'Exceeds the limit (4300 digits) for integer string conversion: '
            'value has 4301 digits; use sys.set_int_max_str_digits() to increase the limit')
        failed = True
    assert failed
print('HTML Unicode, large numeric references and digit-limit errors passed')
