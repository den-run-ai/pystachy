# Adapted from CPython 3.13.16 Lib/test/string_tests.py, class StringLikeTest (which
# test_str.StrTest runs): test_replace, test_replace_uses_two_way_maxcount and
# test_replacement_on_buffer_boundary, commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Each test method becomes a function of the same name, its lines as upstream's.
# checkequal(result, obj, 'replace', *args) calls obj.replace(old, new) or obj.replace(old, new,
# count) (upstream's getattr(obj, methodname)(*args)), prints the result's repr() and asserts it
# is result; upstream's check that a subclass's result is not obj is left out (no str
# subclasses). test_replacement_on_buffer_boundary prints "ok" after its replace() call.
# EXCLUDED upstream cases:
# - test_replace's checkraises() TypeErrors (replace() without arguments, of ints): compile-time
#   errors here
# - Lib/test/test_str.py's StrTest.test_replace: its first line repeats one of
#   string_tests', and its loop over strs of non-ASCII characters (`for left, right in
#   ('ba', '\u0101\u0100', '\U00010301\U00010300')`: unpacking a str of two non-ASCII
#   characters unpacks its bytes, ValueError: too many values to unpack; documented, str is
#   UTF-8 bytes) and its 'replace'.replace("r", 42) TypeError; test_replace_overflow (32-bit
#   platforms) and test_replace_id (CPython-only identity)
import sys


def checkequal(result: str, obj: str, methodname: str, old: str, new: str,
               count: int | None = None) -> None:
    assert methodname == 'replace'
    if count is None:
        realresult = obj.replace(old, new)
    else:
        realresult = obj.replace(old, new, count)
    print(repr(realresult))
    assert result == realresult, (obj, old, new, count)


def test_replace() -> None:
    EQ = checkequal

    # Operations on the empty string
    EQ("", "", "replace", "", "")
    EQ("A", "", "replace", "", "A")
    EQ("", "", "replace", "A", "")
    EQ("", "", "replace", "A", "A")
    EQ("", "", "replace", "", "", 100)
    EQ("A", "", "replace", "", "A", 100)
    EQ("", "", "replace", "", "", sys.maxsize)

    # interleave (from=="", 'to' gets inserted everywhere)
    EQ("A", "A", "replace", "", "")
    EQ("*A*", "A", "replace", "", "*")
    EQ("*1A*1", "A", "replace", "", "*1")
    EQ("*-#A*-#", "A", "replace", "", "*-#")
    EQ("*-A*-A*-", "AA", "replace", "", "*-")
    EQ("*-A*-A*-", "AA", "replace", "", "*-", -1)
    EQ("*-A*-A*-", "AA", "replace", "", "*-", sys.maxsize)
    EQ("*-A*-A*-", "AA", "replace", "", "*-", 4)
    EQ("*-A*-A*-", "AA", "replace", "", "*-", 3)
    EQ("*-A*-A", "AA", "replace", "", "*-", 2)
    EQ("*-AA", "AA", "replace", "", "*-", 1)
    EQ("AA", "AA", "replace", "", "*-", 0)

    # single character deletion (from=="A", to=="")
    EQ("", "A", "replace", "A", "")
    EQ("", "AAA", "replace", "A", "")
    EQ("", "AAA", "replace", "A", "", -1)
    EQ("", "AAA", "replace", "A", "", sys.maxsize)
    EQ("", "AAA", "replace", "A", "", 4)
    EQ("", "AAA", "replace", "A", "", 3)
    EQ("A", "AAA", "replace", "A", "", 2)
    EQ("AA", "AAA", "replace", "A", "", 1)
    EQ("AAA", "AAA", "replace", "A", "", 0)
    EQ("", "AAAAAAAAAA", "replace", "A", "")
    EQ("BCD", "ABACADA", "replace", "A", "")
    EQ("BCD", "ABACADA", "replace", "A", "", -1)
    EQ("BCD", "ABACADA", "replace", "A", "", sys.maxsize)
    EQ("BCD", "ABACADA", "replace", "A", "", 5)
    EQ("BCD", "ABACADA", "replace", "A", "", 4)
    EQ("BCDA", "ABACADA", "replace", "A", "", 3)
    EQ("BCADA", "ABACADA", "replace", "A", "", 2)
    EQ("BACADA", "ABACADA", "replace", "A", "", 1)
    EQ("ABACADA", "ABACADA", "replace", "A", "", 0)
    EQ("BCD", "ABCAD", "replace", "A", "")
    EQ("BCD", "ABCADAA", "replace", "A", "")
    EQ("BCD", "BCD", "replace", "A", "")
    EQ("*************", "*************", "replace", "A", "")
    EQ("^A^", "^"+"A"*1000+"^", "replace", "A", "", 999)

    # substring deletion (from=="the", to=="")
    EQ("", "the", "replace", "the", "")
    EQ("ater", "theater", "replace", "the", "")
    EQ("", "thethe", "replace", "the", "")
    EQ("", "thethethethe", "replace", "the", "")
    EQ("aaaa", "theatheatheathea", "replace", "the", "")
    EQ("that", "that", "replace", "the", "")
    EQ("thaet", "thaet", "replace", "the", "")
    EQ("here and re", "here and there", "replace", "the", "")
    EQ("here and re and re", "here and there and there",
       "replace", "the", "", sys.maxsize)
    EQ("here and re and re", "here and there and there",
       "replace", "the", "", -1)
    EQ("here and re and re", "here and there and there",
       "replace", "the", "", 3)
    EQ("here and re and re", "here and there and there",
       "replace", "the", "", 2)
    EQ("here and re and there", "here and there and there",
       "replace", "the", "", 1)
    EQ("here and there and there", "here and there and there",
       "replace", "the", "", 0)
    EQ("here and re and re", "here and there and there", "replace", "the", "")

    EQ("abc", "abc", "replace", "the", "")
    EQ("abcdefg", "abcdefg", "replace", "the", "")

    # substring deletion (from=="bob", to=="")
    EQ("bob", "bbobob", "replace", "bob", "")
    EQ("bobXbob", "bbobobXbbobob", "replace", "bob", "")
    EQ("aaaaaaa", "aaaaaaabob", "replace", "bob", "")
    EQ("aaaaaaa", "aaaaaaa", "replace", "bob", "")

    # single character replace in place (len(from)==len(to)==1)
    EQ("Who goes there?", "Who goes there?", "replace", "o", "o")
    EQ("WhO gOes there?", "Who goes there?", "replace", "o", "O")
    EQ("WhO gOes there?", "Who goes there?", "replace", "o", "O", sys.maxsize)
    EQ("WhO gOes there?", "Who goes there?", "replace", "o", "O", -1)
    EQ("WhO gOes there?", "Who goes there?", "replace", "o", "O", 3)
    EQ("WhO gOes there?", "Who goes there?", "replace", "o", "O", 2)
    EQ("WhO goes there?", "Who goes there?", "replace", "o", "O", 1)
    EQ("Who goes there?", "Who goes there?", "replace", "o", "O", 0)

    EQ("Who goes there?", "Who goes there?", "replace", "a", "q")
    EQ("who goes there?", "Who goes there?", "replace", "W", "w")
    EQ("wwho goes there?ww", "WWho goes there?WW", "replace", "W", "w")
    EQ("Who goes there!", "Who goes there?", "replace", "?", "!")
    EQ("Who goes there!!", "Who goes there??", "replace", "?", "!")

    EQ("Who goes there?", "Who goes there?", "replace", ".", "!")

    # substring replace in place (len(from)==len(to) > 1)
    EQ("Th** ** a t**sue", "This is a tissue", "replace", "is", "**")
    EQ("Th** ** a t**sue", "This is a tissue", "replace", "is", "**", sys.maxsize)
    EQ("Th** ** a t**sue", "This is a tissue", "replace", "is", "**", -1)
    EQ("Th** ** a t**sue", "This is a tissue", "replace", "is", "**", 4)
    EQ("Th** ** a t**sue", "This is a tissue", "replace", "is", "**", 3)
    EQ("Th** ** a tissue", "This is a tissue", "replace", "is", "**", 2)
    EQ("Th** is a tissue", "This is a tissue", "replace", "is", "**", 1)
    EQ("This is a tissue", "This is a tissue", "replace", "is", "**", 0)
    EQ("cobob", "bobob", "replace", "bob", "cob")
    EQ("cobobXcobocob", "bobobXbobobob", "replace", "bob", "cob")
    EQ("bobob", "bobob", "replace", "bot", "bot")

    # replace single character (len(from)==1, len(to)>1)
    EQ("ReyKKjaviKK", "Reykjavik", "replace", "k", "KK")
    EQ("ReyKKjaviKK", "Reykjavik", "replace", "k", "KK", -1)
    EQ("ReyKKjaviKK", "Reykjavik", "replace", "k", "KK", sys.maxsize)
    EQ("ReyKKjaviKK", "Reykjavik", "replace", "k", "KK", 2)
    EQ("ReyKKjavik", "Reykjavik", "replace", "k", "KK", 1)
    EQ("Reykjavik", "Reykjavik", "replace", "k", "KK", 0)
    EQ("A----B----C----", "A.B.C.", "replace", ".", "----")
    # issue #15534
    EQ('...\u043c......&lt;', '...\u043c......<', "replace", "<", "&lt;")

    EQ("Reykjavik", "Reykjavik", "replace", "q", "KK")

    # replace substring (len(from)>1, len(to)!=len(from))
    EQ("ham, ham, eggs and ham", "spam, spam, eggs and spam",
       "replace", "spam", "ham")
    EQ("ham, ham, eggs and ham", "spam, spam, eggs and spam",
       "replace", "spam", "ham", sys.maxsize)
    EQ("ham, ham, eggs and ham", "spam, spam, eggs and spam",
       "replace", "spam", "ham", -1)
    EQ("ham, ham, eggs and ham", "spam, spam, eggs and spam",
       "replace", "spam", "ham", 4)
    EQ("ham, ham, eggs and ham", "spam, spam, eggs and spam",
       "replace", "spam", "ham", 3)
    EQ("ham, ham, eggs and spam", "spam, spam, eggs and spam",
       "replace", "spam", "ham", 2)
    EQ("ham, spam, eggs and spam", "spam, spam, eggs and spam",
       "replace", "spam", "ham", 1)
    EQ("spam, spam, eggs and spam", "spam, spam, eggs and spam",
       "replace", "spam", "ham", 0)

    EQ("bobob", "bobobob", "replace", "bobob", "bob")
    EQ("bobobXbobob", "bobobobXbobobob", "replace", "bobob", "bob")
    EQ("BOBOBOB", "BOBOBOB", "replace", "bob", "bobby")

    checkequal('one@two!three!', 'one!two!three!', 'replace', '!', '@', 1)
    checkequal('onetwothree', 'one!two!three!', 'replace', '!', '')
    checkequal('one@two@three!', 'one!two!three!', 'replace', '!', '@', 2)
    checkequal('one@two@three@', 'one!two!three!', 'replace', '!', '@', 3)
    checkequal('one@two@three@', 'one!two!three!', 'replace', '!', '@', 4)
    checkequal('one!two!three!', 'one!two!three!', 'replace', '!', '@', 0)
    checkequal('one@two@three@', 'one!two!three!', 'replace', '!', '@')
    checkequal('one!two!three!', 'one!two!three!', 'replace', 'x', '@')
    checkequal('one!two!three!', 'one!two!three!', 'replace', 'x', '@', 2)
    checkequal('-a-b-c-', 'abc', 'replace', '', '-')
    checkequal('-a-b-c', 'abc', 'replace', '', '-', 3)
    checkequal('abc', 'abc', 'replace', '', '-', 0)
    checkequal('', '', 'replace', '', '')
    checkequal('abc', 'abc', 'replace', 'ab', '--', 0)
    checkequal('abc', 'abc', 'replace', 'xy', '--')
    # Next three for SF bug 422088: [OSF1 alpha] string.replace(); died with
    # MemoryError due to empty result (platform malloc issue when requesting
    # 0 bytes).
    checkequal('', '123', 'replace', '123', '')
    checkequal('', '123123', 'replace', '123', '')
    checkequal('x', '123x123', 'replace', '123', '')


def test_replace_uses_two_way_maxcount() -> None:
    A, B = "A"*1000, "B"*1000
    AABAA = A + A + B + A + A
    ABBA = A + B + B + A
    checkequal(AABAA + ABBA,
                    AABAA + ABBA, 'replace', ABBA, "ccc", 0)
    checkequal(AABAA + "ccc",
                    AABAA + ABBA, 'replace', ABBA, "ccc", 1)
    checkequal(AABAA + "ccc",
                    AABAA + ABBA, 'replace', ABBA, "ccc", 2)


def test_replacement_on_buffer_boundary() -> None:
    any_3_nonblank_codepoints = '!!!'
    seven_codepoints = any_3_nonblank_codepoints + ' ' + any_3_nonblank_codepoints
    a = (' ' * 243) + seven_codepoints + (' ' * 7)
    b = ' ' * 6 + chr(256)
    a.replace(seven_codepoints, b)
    print("ok")


test_replace()
test_replace_uses_two_way_maxcount()
test_replacement_on_buffer_boundary()
