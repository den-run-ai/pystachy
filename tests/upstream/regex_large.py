# Adapted from CPython 3.13.16 Lib/test/test_re.py, ReTests, commit
# cbc944f4bc59639a444dd971c737788ba2283a91: test_stack_overflow,
# test_bug_418626, test_big_codesize and test_search_anchor_at_beginning.
# PSF License v2; see CPYTHON-LICENSE.txt here and THIRD_PARTY_NOTICES.
# Run by tools/re_upstream_large.py under CPython and compiled JIT/AOT with normal GC.
# These retain upstream's sizes, outside tests/*.py's collect-every-allocation runs.
# unittest assertions become assert; the upstream anchor CPUStopwatch bound is omitted
# (the runner has a generous wall-clock timeout, not a machine-dependent speed gate).
import re


def test_stack_overflow() -> None:
    for pattern, subject in [('(x)*', 50000 * 'x'), ('(x)*y', 50000 * 'x' + 'y'),
                             ('(x)*?y', 50000 * 'x' + 'y')]:
        match = re.match(pattern, subject)
        assert match is not None
        assert match.group(1) == 'x'
        print('test_stack_overflow', pattern, match.span(), match.group(1))


def test_bug_418626() -> None:
    for pattern, subject, end in [('.*?c', 10000 * 'ab' + 'cd', 20001),
                                 ('.*?cd', 5000 * 'ab' + 'c' + 5000 * 'ab' + 'cde', 20003),
                                 ('.*?cd', 20000 * 'abc' + 'de', 60001)]:
        match = re.match(pattern, subject)
        assert match is not None
        assert match.end(0) == end
        print('test_bug_418626', match.span())
    match = re.search('(a|b)*?c', 10000 * 'ab' + 'cd')
    assert match is not None
    assert match.end(0) == 20001
    print('test_bug_418626', match.span(), match.group(1))


def test_big_codesize() -> None:
    pattern = re.compile('|'.join(['%d' % x for x in range(10000)]))
    for subject in ['1000', '9999']:
        match = pattern.match(subject)
        assert match is not None
        print('test_big_codesize', subject, match.span(), match.group(0))


def test_search_anchor_at_beginning() -> None:
    subject = 'x' * 10**7
    for pattern in [r'\Ay', r'^y']:
        assert re.search(pattern, subject) is None
        assert re.split(pattern, subject) == [subject]
        assert re.findall(pattern, subject) == []
        assert [match.span() for match in re.finditer(pattern, subject)] == []
        assert re.sub(pattern, '', subject) == subject
        print('test_search_anchor_at_beginning', pattern, len(subject))


test_stack_overflow()
print('PASS ReTests.test_stack_overflow')
test_bug_418626()
print('PASS ReTests.test_bug_418626')
test_big_codesize()
print('PASS ReTests.test_big_codesize')
test_search_anchor_at_beginning()
print('PASS ReTests.test_search_anchor_at_beginning')
