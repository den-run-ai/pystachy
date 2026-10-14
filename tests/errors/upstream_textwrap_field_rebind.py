# error: expected bool, got int
# CPython 3.13.16 test_textwrap.LongWordTestCase.test_nobreak_long assigns integer 0
# to the default Boolean field. The compiled port's field keeps its original type.
from textwrap import TextWrapper

wrapper = TextWrapper()
wrapper.break_long_words = 0
