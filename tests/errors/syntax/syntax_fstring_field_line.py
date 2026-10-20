# error: syntax_fstring_field_line.py:6: error: invalid decimal literal
# an error in a field is reported on its own line
def f():
    return f'''
{
(123_a)
}'''


print("ran")
