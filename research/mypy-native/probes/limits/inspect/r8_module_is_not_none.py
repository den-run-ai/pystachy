# the same idiom with a module lib/ has had for long: the test "module is not None"
try:
    import keyword
except ImportError:
    keyword = None

if keyword is not None:
    print(keyword.iskeyword("class"))
