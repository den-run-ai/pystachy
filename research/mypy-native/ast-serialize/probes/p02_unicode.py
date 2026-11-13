import unicodedata

print(unicodedata.normalize("NFKC", "ﬁx"), unicodedata.normalize("NFKC", "x⁵"))
print(unicodedata.category("é"), " ".isspace(), "\x1c".isspace())
print("ab_1".isalnum(), "é".isalnum(), "²".isalnum())
print(unicodedata.unidata_version)
