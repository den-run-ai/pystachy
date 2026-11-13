# __file__: "'__file__' is not supported"; the test parses its own file by its path from the
# repository's root, where the tests run
print(__file__.endswith(".py"))
