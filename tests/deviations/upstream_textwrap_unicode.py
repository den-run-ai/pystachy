# CPython 3.13.16 Lib/test/test_textwrap.py, commit
# cbc944f4bc59639a444dd971c737788ba2283a91. PSF License v2; see
# tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# Original inputs of two complete upstream methods whose line breaks differ
# because Pystachy's widths count UTF-8 bytes (#120). Print the raw results;
# the expected CPython lists below are not normalized into compiled successes.
from textwrap import wrap


# test_textwrap.WrapTestCase.test_umlaut_followed_by_dash
text = 'aa \xe4\xe4-\xe4\xe4'
# CPython expects ['aa \xe4\xe4-', '\xe4\xe4'].
print('test_umlaut_followed_by_dash', wrap(text, 7))


# test_textwrap.WrapTestCase.test_narrow_non_breaking_space
text = 'This is a sentence with non-breaking\u202fspace.'
# CPython expects ['This is a sentence', 'with non-', 'breaking\u202fspace.'].
# This first upstream assertion already agrees under Pystachy.
print('test_narrow_non_breaking_space True', wrap(text, 20, break_on_hyphens=True))
# CPython expects ['This is a sentence', 'with', 'non-breaking\u202fspace.'].
print('test_narrow_non_breaking_space False', wrap(text, 20, break_on_hyphens=False))
