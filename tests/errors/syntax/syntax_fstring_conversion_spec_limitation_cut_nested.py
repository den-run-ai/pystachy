# error: syntax_fstring_conversion_spec_limitation_cut_nested.py:5: error: f-string: invalid conversion character 'f': expected 's', 'r', or 'a'
# the spec of that field ends where its nested fields and their specs end: a '#' in a nested
# spec is text, not a comment
x = 1
print(f"{x!f:{x:#x}{é}}{x
