# error: only UTF-8 and Latin-1 files are supported, not encoding='latin.1'
# "." is kept by CPython's normalization: "latin.1" is no alias, and "latin_1" only a module name
f = open("x.txt", "w", encoding="latin.1")
