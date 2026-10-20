# ord() of a longer string: the message counts characters, not UTF-8 bytes
print(ord("\u00e9"), ord("\u20ac"), ord("\U0001f600"))
print(ord("\u00e9a\U0001f600"))
