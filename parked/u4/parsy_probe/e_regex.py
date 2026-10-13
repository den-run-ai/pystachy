edit("regex: exp and group change type when rebound (a str to a Pattern, an int or str to a tuple)", "group: int | str | tuple = 0", "group: int | str = 0")
edit("regex: rebinding", '''    if isinstance(exp, (str, bytes)):
        exp = re.compile(exp, flags)
    if isinstance(group, (str, int)):
        group = (group,)
''', '''    pat = re.compile(exp, flags)  # pystachy: a name keeps its type
''')
edit("regex: rebinding", "match = exp.match(stream, index)", "match = pat.match(stream, index)")
edit("regex: rebinding", "match.group(*group)", "match.group(group)")
edit("regex: rebinding", "Result.failure(index, exp.pattern)", "Result.failure(index, pat.pattern)")
