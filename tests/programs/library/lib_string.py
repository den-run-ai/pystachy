# lib/string.py: CPython 3.13's string with its marked edits (lib/README.md), against CPython's
# own: the constants, capwords() and Template (cases after CPython's Lib/test/test_string.py)
import string
from string import Template, capwords

print(string.whitespace == " \t\n\r\x0b\x0c", string.ascii_lowercase, string.ascii_uppercase)
print(string.ascii_letters, string.digits, string.hexdigits, string.octdigits)
print(string.punctuation, len(string.printable), repr(string.printable[-8:]))
print(string.__all__)
for w in ["abc def ghi", "abc\tdef\nghi", "abc\t   def  \nghi", "ABC DEF GHI", "ABC-DEF-GHI",
          "ABC-def DEF-ghi GHI", "   aBc  DeF   ", "\taBc\tDeF\t", "", " ", "x"]:
    print(repr(capwords(w)), repr(capwords(w, "\t")))
print(repr(capwords("ABC-def DEF-ghi GHI", "-")), repr(capwords("a--b", "-")), repr(capwords("hello world", None)))

s = Template("$who likes to eat a bag of $what worth $$100")
print(s.substitute({"who": "tim", "what": "ham"}))
print(s.substitute({"who": "tim", "what": "ham"}), "|", s.template)
try:
    s.substitute({"who": "tim"})
except KeyError as e:
    print("KeyError", e)
s = Template("$who likes ${what} for ${meal}")
print(s.substitute({"who": "tim", "what": "ham", "meal": "dinner"}))
try:
    s.substitute({"who": "tim", "what": "ham"})
except KeyError as e:
    print("KeyError", repr(e))
print(Template("$WHO likes ${WHAT} for ${MEAL}").substitute({"WHO": "tim", "WHAT": "ham", "MEAL": "dinner"}))
print(Template("$_wh0_ likes ${_w_h_a_t_} for ${mea1}").substitute({"_wh0_": "tim", "_w_h_a_t_": "ham", "mea1": "dinner"}))
print(Template("$who likes to eat a bag of $$what worth $$100").substitute({"who": "tim", "what": "ham"}))
print(Template("$who likes $$").substitute({"who": "tim", "what": "ham"}))
p = Template("%(foo)s $foo ${foo}")
print(p.substitute({"foo": "baz"}), "|", p.safe_substitute({"foo": "baz"}))

# values that are no strs: str() of each
c = Template("tim has eaten $count bags of ham today")
print(c.substitute({"count": 7}), "|", c.safe_substitute({"count": 7}))
print(Template("tim has eaten ${count} bags of ham today").substitute({"count": 7}))
tup = Template("$who ate ${meal}")
d2 = {"who": ("tim", "fred"), "meal": ("ham", "kung pao")}
print(tup.substitute(d2), "|", tup.safe_substitute(d2))
print(Template("$x and $y").substitute(x=1.5, y=2.25), Template("${a}${b}").substitute(a=True, b=False))
nones: dict[str, str | None] = {"n": None}
print(Template("$xs").substitute(xs=[1, 2, 3]), Template("$n").safe_substitute(nones))

st = Template("$who likes ${what} for ${meal}")
print(st.safe_substitute({"who": "tim"}))
print(st.safe_substitute({"what": "ham"}))
print(st.safe_substitute({"what": "ham", "meal": "dinner"}))
print(st.safe_substitute({"who": "tim", "what": "ham"}))
print(st.safe_substitute({"who": "tim", "what": "ham", "meal": "dinner"}))

# keyword arguments, alone and with a mapping (they come first), also named mapping and self
k = Template("$who likes $what")
print(k.substitute(who="tim", what="ham"), "|", k.substitute({"who": "tim"}, what="ham"))
print(k.substitute({"who": "fred", "what": "kung pao"}, who="tim", what="ham"))
print(k.safe_substitute(who="tim", what="ham"), "|", k.safe_substitute({"who": "tim"}, what="ham"))
print(k.safe_substitute({"who": "fred", "what": "kung pao"}, who="tim", what="ham"), "|", k.safe_substitute(what="ham"))
m = Template("the mapping is $mapping")
print(m.substitute({"foo": "none"}, mapping="bozo"), "|", m.substitute({"mapping": "one"}, mapping="two"))
print(m.safe_substitute({"foo": "none"}, mapping="bozo"), "|", m.safe_substitute({"mapping": "one"}, mapping="two"))
print(Template("the self is $self").substitute(self="bozo"), "|", Template("the self is $self").safe_substitute(self="bozo"))
print(k.substitute({"who": "ann", "what": "tea"}, extra="unused"), "|", k.substitute(who=1, what=2))
try:
    k.substitute({"who": "ann"}, extra="x")
except KeyError as e:
    print("KeyError", e)
try:
    k.substitute(what="ham")
except KeyError as e:
    print("KeyError", e)

# no mapping, no keywords
print(Template("100$$ and no names").substitute(), "|", Template("$a ${b} $$").safe_substitute())
try:
    Template("$gift").substitute()
except KeyError as e:
    print("KeyError", e)


class Upper:
    # a mapping of the program's: __getitem__, which may raise KeyError
    def __getitem__(self, name: str) -> str:
        if name.startswith("x"):
            raise KeyError(name)
        return name.upper()


print(Template("$abc and ${de}").substitute(Upper()), "|", Template("$abc ${xyz} $x").safe_substitute(Upper()))
print(Template("$abc and $xyz").substitute(Upper(), xyz="kw"))
try:
    Template("$abc and $xyz").substitute(Upper())
except KeyError as e:
    print("KeyError", e)

# invalid placeholders: ValueError with the line and column
for t in ["$who likes $", "$who likes ${what)", "$who likes $100", "$who likes $\u0131",
          "$", "${", "${}", "$ x", "a\n$b\n$ c", "line one\nline two\n\nx $1 y",
          "$a\r\n$b\r\n$", "${a}${b c}"]:
    try:
        print(Template(t).substitute({"who": "tim", "what": "ham", "a": "1", "b": "2"}))
    except ValueError as e:
        print("ValueError", e)
    print(repr(Template(t).safe_substitute({"who": "tim", "a": "1"})), Template(t).is_valid())

print(Template("$who likes to eat a bag of ${what} worth $$100").is_valid())
print(Template("$who likes to eat a bag of ${what} worth $100").is_valid())
print(Template("$who likes to eat a bag of ${what} worth $$100").get_identifiers())
print(Template("$who likes to eat a bag of ${what} worth $$100; ${who} likes to eat a bag of $what worth $$100").get_identifiers())
print(Template("$who likes to eat a bag of ${what} worth $100").get_identifiers(), Template("").get_identifiers())
print(Template("no placeholders").is_valid(), Template("$$").get_identifiers(), Template("$a$b${c}d").get_identifiers())

# the class attributes and the pattern
print(Template.delimiter, Template.idpattern, Template.braceidpattern, int(Template.flags))  # (an int: deviations/)
pat = Template.pattern
print(pat.pattern)
print(pat.flags, pat.groups, pat.groupindex)
print(Template("$x").pattern.pattern == pat.pattern, Template("a$b").template)
mo = pat.search("say ${hello} $$ $x")
print(mo.group("braced"), mo.span(), [m.group() for m in pat.finditer("say ${hello} $$ $x $")])
u = Template("$who likes $what")
print(u.substitute({"who": "t\xffm", "what": "f\xfe\x0ced"}))
print(Template("caf\xe9 $x \u20ac$y").substitute(x="cr\xe8me", y="5"))
print(repr(Template.pattern))
t2 = Template("$a")
print(t2.pattern is Template.pattern)
t2.template = "now ${b} and $$"
print(t2.substitute(b="x"), t2.get_identifiers(), t2.is_valid())
print(Template("$who").substitute({"who": "a"}, who="b"), Template("$x$y").safe_substitute({"x": 1}, y=2))
