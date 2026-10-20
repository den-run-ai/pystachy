# error: upstream_dataclasses_order_false.py:16: error: '<' not supported between instances of 'C0' and 'C0'
# CPython 3.13.16 Lib/test/test_dataclasses/__init__.py, TestCase.test_1_field_compare
# (assertRaisesRegex(TypeError, "not supported between instances of 'C0' and 'C0'"), fn(cls(0),
# cls(0)) with fn = lambda a, b: a < b, for a @dataclass without order=True),
# commit cbc944f4bc59639a444dd971c737788ba2283a91.
# PSF License v2; see tests/upstream/CPYTHON-LICENSE.txt and THIRD_PARTY_NOTICES.
# CPython raises this TypeError where the comparison runs; Pystachy rejects it at compile time,
# with CPython's message.
from dataclasses import dataclass


@dataclass
class C0:
    x: int

C0(0) < C0(0)
