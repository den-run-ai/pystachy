# CPython 3.13.16 Lib/test/test_dictviews.py (commit cbc944f4bc59639a444dd971c737788ba2283a91,
# SHA-256 f6e290a9cda996fd2531e20902cb99fd8785da069a31e27038daed194b3295e2),
# made mechanically by tools/cpython_test_methods.py: unittest scaffolding becomes plain
# statements that keep each test's inputs and assertions (tests/upstream/core-sweep.md).
# Tests: DictSetTest.test_dict_mixed_keys_items.
class DictSetTest:

    def test_dict_mixed_keys_items(self):
        d = {(1, 1): 11, (2, 2): 22}
        e = {1: 1, 2: 2}
        assert d.keys() == e.items()
        assert d.items() != e.keys()


def _DictSetTest__test_dict_mixed_keys_items():
    t = DictSetTest()
    t.test_dict_mixed_keys_items()
    print('ok DictSetTest.test_dict_mixed_keys_items')


_DictSetTest__test_dict_mixed_keys_items()
