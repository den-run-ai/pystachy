# error: syntax_fstring_comment.py:4: error: '{' was never closed
# a comment in a replacement field runs to the end of the line, so the field is never closed
x = 5
print(f"a{x#comment}b")
