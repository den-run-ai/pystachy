# error: upstream_call_no_suggestion_varargs.py:11: error: foo() got an unexpected keyword argument 'orgs'
# CPython 3.13.16 Lib/test/test_call.py, TestErrorMessagesSuggestions.test_unexpected_keyword_suggestion_valid_positions ("orgs"),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython suggests no keyword here (its message has no "Did you mean"); a call whose
# arguments do not fit is a compile-time error here, with CPython's message.
def foo(blech=None, /, aaa=None, *args, late1=None):
    pass


foo(**{"orgs": None})
