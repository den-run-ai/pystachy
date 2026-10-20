# lib/textwrap.py: CPython 3.13's textwrap with its marked edits (lib/README.md), against
# CPython's own. Cases after CPython's Lib/test/test_textwrap.py.
import re
import textwrap
from textwrap import TextWrapper, dedent, fill, indent, shorten, wrap

text = "Hello there, how are you this fine day?  I'm glad to hear it!"
for w in [12, 42, 80]:
    print(w, wrap(text, w))
print(wrap("", 6), wrap("", 6, drop_whitespace=False), wrap("", 6, initial_indent="++"))
print(wrap("   ", 6), wrap("   ", 6, drop_whitespace=False))

mess = """\
This is a paragraph that already has
line breaks.  But some of its lines are much longer than the others,
so it needs to be wrapped.
Some lines are \ttabbed too.
What a mess!
"""
wr = TextWrapper(45, fix_sentence_endings=True)
print(wr.wrap(mess))
print(wr.fill(mess))
print(wrap("\tTest\tdefault\t\ttabsize.", 80))
print(wrap("\tTest\tcustom\t\ttabsize.", 80, tabsize=4))
print(wrap("\tTest\tno expand.", 80, expand_tabs=False))
print(wrap("\tTest\tkeep\nwhitespace.", 80, expand_tabs=False, replace_whitespace=False))

fs = TextWrapper(60, fix_sentence_endings=True)
for t in ["A short line. Note the single space.", "Well, Doctor? What do you think?", "Well, Doctor?\nWhat do you think?",
          'I say, chaps! Anyone for "tennis?"\nHmmph!', 'And she said, "Go to hell!"\nCan you believe that?']:
    print(fs.wrap(t))
fs.width = 20
print(fs.wrap('I say, chaps! Anyone for "tennis?"\nHmmph!'))
print(fs.wrap('And she said, "Go to hell!"\nCan you believe that?'))

hy = "Did you say \"supercalifragilisticexpialidocious?\"\nHow *do* you spell that odd word, anyways?"
for w in [25, 30, 35, 50]:
    print(w, wrap(hy, w))
print(wrap(hy, 25, break_on_hyphens=False))
print(wrap("this-is-a-useful-feature-for-reformatting-posts-from-tim-peters'ly", 41))
print(wrap("this-is-a-useful-feature-for-reformatting-posts-from-tim-peters'ly", 41, break_on_hyphens=False))
print(wrap("Em-dashes should be written -- thus.", 10), wrap("Em-dashes should be written -- thus.", 11))
print(wrap("Em-dashes should be written -- thus.", 12), wrap("Em-dashes should be written -- thus.", 15))
print(wrap("Em-dashes should be written -- thus.", 16), wrap("Em-dashes should be written -- thus.", 29))
print(wrap("You can also do--this or even---this.", 15), wrap("Here's an -- em-dash and--here's another---and another!", 10))
print(wrap("and then--bam!--he was gone", 14), wrap("--this-- is a test--", 10))
print(wrap("the -b option!", 10), wrap("the -b option!", 4), wrap("the -option!", 4))
print(wrap("what the -- -b option!", 10), wrap("what the --b option!", 10))
print(wrap("yaba-daba-doo", 5), wrap("yaba-daba-doo", 6), wrap("aa bb-cc", 7))
print(wrap("A long piece of text, with a URL http://example.com/a-very-long-url-that-will-not-fit", 20))
print(wrap("A long piece of text, with a URL http://example.com/a-very-long-url-that-will-not-fit", 20, break_long_words=False))
print(wrap("Hello there -- you goof-ball, use the -b option!", 1))

for x in ["This is a short paragraph.", "This is a short line"]:
    print(wrap(x, 30, initial_indent="  * ", subsequent_indent="    "))
long = "This paragraph will be filled, first without any indentation, and then with some (including a hanging indent)."
print(fill(long, 40))
print(fill(long, 40, initial_indent="  "))
print(fill(long, 40, initial_indent="  ", subsequent_indent="    "))
print(fill(long, 40, initial_indent="* ", subsequent_indent=""))
print(wrap(long, 12, max_lines=2), wrap(long, 12, max_lines=3, placeholder="..."))
print(wrap(long, 12, max_lines=1, placeholder=" [truncated]"))
print(wrap("Hello there, how are you this fine day?", 12, max_lines=4))
print(wrap("  This text has leading spaces.  ", 10, drop_whitespace=False))
for m in [1, 2, 3, 4]:
    print(m, wrap(text, 12, max_lines=m), wrap(text, 12, max_lines=m, placeholder=" ..."))
try:
    wrap(text, 0)
except ValueError as e:
    print("ValueError:", e)
try:
    wrap(text, 12, max_lines=1, placeholder=" [truncated]...", initial_indent="    ")
except ValueError as e:
    print("ValueError:", e)

w2 = TextWrapper(width=20, initial_indent="> ", subsequent_indent=". ")
for t in [text, mess, "word " * 9]:
    print(w2.wrap(t))
w2.width = 30
w2.break_long_words = False
print(w2.fill("supercalifragilisticexpialidocious is long " * 2))
print(w2.width, w2.initial_indent, w2.subsequent_indent, w2.expand_tabs, w2.max_lines, w2.placeholder)
print(TextWrapper.wordsep_re.pattern == textwrap.TextWrapper.wordsep_re.pattern)
print(TextWrapper.wordsep_simple_re.split("Hello there -- you goof-ball"))
print(textwrap.TextWrapper(width=45)._split("Hello there -- you goof-ball, use the -b option!"))
print(textwrap.TextWrapper(width=45, break_on_hyphens=False)._split("Hello there -- you goof-ball, use the -b option!"))
print(TextWrapper.unicode_whitespace_trans)

print(shorten("Hello  world!", width=12), shorten("Hello  world!", width=11))
print(shorten(text, 40), shorten(text, 40, placeholder="..."), shorten("   ", 10))
print(shorten("The quick brown fox jumped over the lazy dog.", 25, placeholder=" (...)"))
try:
    shorten("Hello world!", 8, placeholder=" [...] [...]")
except ValueError as e:
    print("ValueError:", e)

for t in ["Hello there.\nHow are ya?\nOh good, I'm glad.", "Hello there.\n\nBoo!", "Hello there.\n  This is indented.",
          "  Hello there.\n  How are ya?\n  Oh good.\n", "  Hello there.\n\n  How are ya?\n  Oh good.\n",
          "  Hello there.\n  \n  How are ya?\n  Oh good.\n", "     Line one.\n   Line two.\n     Line three.\n",
          "\tHello there.\n\tHow are ya?\n\tOh good.", "  \tHello there.\n  \tHow are ya?\n  \tOh good.",
          "\t  Hello there.\n  \tHow are ya?", "  hello\tthere\n  how are\tyou?", "    a\n      b\n    c\n", "\n\n  x\n   y\n\n",
          "  \n\t\n  x\n", ""]:
    print(repr(dedent(t)))

for t in ["", "\n", "  \n", "Hi.\nThis is a test.\nTesting.", "\nHi.\nThis is a test.\n\nTesting.\n", "Hi.\r\nThis is a test.\r\nTesting.\r\n"]:
    print(repr(indent(t, "  ")), repr(indent(t, "> ")))
print(repr(indent("Hi.\nThis is a test.\nTesting.", "+ ", lambda line: True)))
print(repr(indent("\nHi.\nThis is a test.\n\nTesting.\n", "+ ", lambda line: line.strip() == "Testing.")))
print(repr(indent("a\n  b\nc\n", ">", str.isspace)))

# the class attributes, and a wrapper's own values for them, which no other wrapper sees
print(TextWrapper.sentence_end_re.pattern, TextWrapper.wordsep_simple_re.pattern)
w3 = TextWrapper(12)
w3.max_lines = 2
w3.placeholder = " ..."
print(w3.wrap(text))
w3.max_lines = None
print(w3.wrap(text))
w3.wordsep_re = re.compile(r"(\s+)")
w3.unicode_whitespace_trans = {ord("x"): ord("y")}
print(w3.wrap("aa-bb cc-dd xx\txx"), TextWrapper(12).wrap("aa-bb cc-dd xx\txx"))
print(w3.wordsep_re.pattern, TextWrapper(5).wordsep_re.pattern == TextWrapper.wordsep_re.pattern)
