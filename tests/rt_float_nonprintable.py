# float() of a string with a soft hyphen and a zero-width space: their repr() escapes in the message
print(float("1.\u00ad5\u200b"))
