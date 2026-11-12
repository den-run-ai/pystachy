# textwrap's patterns are Pattern objects from the moment the module loads, with CPython's flags
# and groups, and equal to (and hashing as) the same patterns compiled afresh, whichever of the
# two an operation uses first.
import re
import textwrap

W = textwrap.TextWrapper
late = W.sentence_end_re
print(late == re.compile(late.pattern), hash(late) == hash(re.compile(late.pattern)))
for name, p in [("wordsep", W.wordsep_re), ("simple", W.wordsep_simple_re), ("sentence", W.sentence_end_re),
                ("only", textwrap._whitespace_only_re), ("leading", textwrap._leading_whitespace_re)]:
    q = re.compile(p.pattern, p.flags & ~re.UNICODE)
    print(name, p.flags, p.groups, p.groupindex, q.flags == p.flags, q.groups == p.groups, q == p, p == q, hash(p) == hash(q))
    print(len({p: 1, q: 2}), p != q, p is q, repr(p)[:40])
print(W.wordsep_simple_re.split("a  b\tc"), W.sentence_end_re.search("so. Then") is None, W.sentence_end_re.search('so."') is not None)
print(textwrap._whitespace_only_re.sub("", " \t\nx\n  "), textwrap._leading_whitespace_re.findall("  a\n\tb\nc"))
print(textwrap.fill("The quick brown fox -- jumped over the lazy-dog. And then? It slept well.", 20, fix_sentence_endings=True))
print(textwrap.dedent("    a\n      b\n   \n    c"))
print(textwrap.wrap("alpha beta-gamma delta", 8, break_on_hyphens=False))
print(textwrap.shorten("Hello  world, this is a test", 15), textwrap.indent("a\n\nb\n", "> "))
