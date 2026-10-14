# CPython 3.13.16 Lib/test/test_html.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91, SHA-256
# 919a7200a93ff375ed09ee1125b1c976b487c49e8c43f58690977878211ed45c.
# Complete assertion sets from HtmlTests.test_escape and test_unescape.
# Adaptations: unittest assertions become assert, helpers move to module scope,
# and dynamic %-format strings are expanded into equivalent constant formats.
# The four non-ASCII expected characters are a list, rather than str iteration.
# PSF License Version 2; see THIRD_PARTY_NOTICES.
import html


def check(text: str, expected: str) -> None:
    assert html.unescape(text) == expected, text


def check_num(num: int, expected: str) -> None:
    for text in ['&#%d' % num, '&#%d;' % num, '&#x%x' % num, '&#x%x;' % num]:
        check(text, expected)


def test_escape() -> None:
    assert html.escape('\'<script>"&foo;"</script>\'') == (
        '&#x27;&lt;script&gt;&quot;&amp;foo;&quot;&lt;/script&gt;&#x27;')
    assert html.escape('\'<script>"&foo;"</script>\'', False) == (
        '\'&lt;script&gt;"&amp;foo;"&lt;/script&gt;\'')


def test_unescape() -> None:
    check('no character references', 'no character references')
    check('&\n&\t& &&', '&\n&\t& &&')
    check('&0 &9 &a &0; &9; &a;', '&0 &9 &a &0; &9; &a;')
    for x in ['&', '&#', '&#x', '&#X', '&#y', '&#xy', '&#Xy']:
        check(x, x)
        check(x+';', x+';')
    for num, char in zip([65, 97, 34, 38, 0x2603, 0x101234],
                         ['A', 'a', '"', '&', '\u2603', '\U00101234']):
        # Same twelve formats, inputs and suffix combinations as upstream.
        texts = ['&#%d' % num, '&#%07d' % num, '&#%d;' % num, '&#%07d;' % num,
                 '&#x%x' % num, '&#x%06x' % num, '&#x%x;' % num, '&#x%06x;' % num,
                 '&#x%X' % num, '&#x%06X' % num, '&#X%x;' % num, '&#X%06x;' % num]
        for text in texts:
            check(text, char)
            for end in [' ', 'X']:
                check(text+end, char+end)
    for cp in [0xD800, 0xDB00, 0xDC00, 0xDFFF, 0x110000]:
        check_num(cp, '\uFFFD')
    for cp in [0x1, 0xb, 0xe, 0x7f, 0xfffe, 0xffff, 0x10fffe, 0x10ffff]:
        check_num(cp, '')
    for num, ch in zip([0x0d, 0x80, 0x95, 0x9d], ['\r', '\u20ac', '\u2022', '\x9d']):
        check_num(num, ch)
    check_num(0, '\uFFFD')
    check_num(9, '\t')
    check_num(1000000000000000000, '\uFFFD')
    for e in ['&quot;;', '&#34;;', '&#x22;;', '&#X22;;']:
        check(e, '";')
    for e in ['&quot;quot;', '&#34;quot;', '&#x22;quot;', '&#X22;quot;']:
        check(e, '"quot;')
    for e in ['&quot', '&#34', '&#x22', '&#X22']:
        check(e*3, '"""')
        check((e+';')*3, '"""')
    for e in ['&amp', '&amp;', '&AMP', '&AMP;']:
        check(e, '&')
    for e in ['&Amp', '&Amp;']:
        check(e, e)
    check('&svadilfari;', '&svadilfari;')
    check('&notit', '¬it')
    check('&notit;', '¬it;')
    check('&notin', '¬in')
    check('&notin;', '∉')
    check('&notReallyAnExistingNamedCharacterReference;',
          '¬ReallyAnExistingNamedCharacterReference;')
    check('&CounterClockwiseContourIntegral;', '∳')
    check('&acE;', '\u223E\u0333')
    check('&acE', '&acE')
    check('&#123; ' * 1050, '{ ' * 1050)
    check('&Eacuteric&Eacute;ric&alphacentauri&alpha;centauri',
          'ÉricÉric&alphacentauriαcentauri')
    check('&co;', '&co;')


test_escape()
test_unescape()
print('HtmlTests.test_escape and test_unescape passed')
