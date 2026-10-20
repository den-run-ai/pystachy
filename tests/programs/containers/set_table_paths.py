# Set operations whose outcome shows in the order CPython's set table iterates: an insertion that
# passed a deleted slot (a dummy) goes there, in sets of ints and of strs; pop() takes the next
# element from where the last one was, past the table's end to its start; s -= t of a t more than
# 8 times larger, and s.difference(d) of a dict d over 4 times smaller than s, which CPython
# computes in other ways than for operands of like sizes.
s = {1, 9}            # 9 collides with 1 and takes the next slot
s.discard(1)
s.add(17)             # 17 collides too: it goes into 1's old slot, before 9
print(list(s))
s.add(25)
s.discard(9)
s.add(33)
print(list(s))
words = {"a", "b", "c"}
for w in ["a", "b"]:
    words.discard(w)
    words.add(w + w)
print(sorted(words), len(words))
p = {5, 6}
print(p.pop(), p.pop())
p.add(1)              # the next pop() starts after slot 6, wraps to the table's start
p.add(3)
print(p.pop(), p.pop(), p)
small = {3, 50, 97}
small -= set(range(0, 100, 2))   # 50 elements: more than 8 times as many
print(sorted(small), list(small))
big = set(range(40))
print(list(big.difference({7: "x", 30: "y", 99: "z"})))   # over 4 times larger than the dict
print(list(set(range(8)).difference({1: "a", 2: "b", 3: "c", 4: "d"})))
mixed = set(range(20, 0, -3))
mixed -= {5, 11}
print(list(mixed), list(mixed.difference({2: 0})))
