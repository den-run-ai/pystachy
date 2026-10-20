# quotes in a format spec are fill characters; strings inside a field use the other quote
x = 5
print(f"{x:'>4}", 'z')
print(f"{x!r:'>4}", f'{"a"!r}', 'z')
print(f"{x:{'*'}>4}", f'{x:">4}')
d = {'k': 1}
print(f"{d['k']:>3}|{x=}|{x=:>3}|{ {'a': x}['a'] }")
print(f"{x:\">4}")
