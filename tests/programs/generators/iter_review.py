import builtins as b
from builtins import iter as make_iter
import csv
import io
import shlex
from collections import deque

print(next(b.iter([10, 20])), next(make_iter([30, 40])))
s = io.StringIO('one\ntwo\nthree\n')
it = iter(s)
print(it is s, s.tell(), next(it).strip(), s.tell())
print(s.readline().strip(), next(s).strip(), next(it, 'end'))
s.seek(0)
print(next(it).strip())
s.close()
try:
    next(it)
except ValueError as e:
    print(e)

lex = shlex.shlex('one two three', posix=True)
it2 = iter(lex)
print(it2 is lex, next(it2), lex.get_token(), next(lex), next(it2, 'end'))
lex = shlex.shlex('one two', posix=False)
print(next(lex), list(lex))

rows = ['a,b', '"c', 'd",e', '"broken']
r = csv.reader(rows, strict=True)
it3 = iter(r)
print(it3 is r, r.line_num, next(it3), r.line_num)
print(next(r), r.line_num)
try:
    next(r)
except csv.Error as e:
    print(str(e), r.line_num)
print(next(r, ['end']))
r = csv.reader(['a,b', 'c,d', 'e,f'])
for row in r:
    print(row, r.line_num)
    break
print(list(r))

q = deque([1, 2, 3])
iq = iter(q)
print(next(iq))
q[1] = 7
print(next(iq))
q.reverse()
print(next(iq), next(iq, -1))
q.append(9)
try:
    next(iq)
except RuntimeError as e:
    print(e)
q = deque([1, 2, 3])
iq2 = iter(q)
q.popleft()
try:
    next(iq2)
except RuntimeError as e:
    print(e)
