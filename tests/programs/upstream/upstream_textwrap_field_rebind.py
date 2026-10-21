# CPython 3.13.16 test_textwrap.LongWordTestCase.test_nobreak_long assigns integer 0
# to the default Boolean field: the field holds bool | int, as if annotated.
from textwrap import TextWrapper

wrapper = TextWrapper()
wrapper.break_long_words = 0
wrapper.width = 10
print(wrapper.wrap("a supercalifragilistic word"))
