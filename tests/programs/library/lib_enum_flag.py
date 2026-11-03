# Flag classes: members of int values (auto()'s are powers of two), the class's single-bit members as
# its iteration and len(), composite members by |, & and ^, kept as one object each, ~ within the
# members' bits, in and iteration of a flag, CPython's repr(), str(), format() and hash(), and its
# ValueError for a value with bits no member has (boundary STRICT) and TypeError for an int operand
from enum import Flag, auto
class P(Flag):
    R = 4
    W = 2
    X = 1
    RW = 6
class Q(Flag):
    A = auto()
    B = auto()
    C = auto()
print(list(P), list(Q), Q.A, Q.B.value, Q.C.value)
rw = P.R | P.W
print(repr(rw), str(rw), rw is P.RW, rw.name, rw.value, P.R in rw, P.X in rw, bool(P(0)), repr(P(0)), list(rw), len(rw))
print(repr(P.R | P.X), repr(~P.R), repr(P.R & P.W), repr(P.RW ^ P.R), repr(P(7)), str(P(7)))
try:
    P(8)
except ValueError as e:
    print("ValueError", e)
print(len(P), repr(P), 6 in P, 8 in P, P.RW in P, (Q.A | Q.B) is (Q.B | Q.A), hash(Q.A) == hash("A"))
print(format(Q.A), f"{Q.A | Q.B:>9}|", repr(~Q.A), repr(~(Q.A | Q.B)), str(Q(0)))
try:
    print(Q.A | 1)
except TypeError as e:
    print("TypeError", e)
