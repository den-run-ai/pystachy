# error: comprehension_empty_tuple.py:6: error: cannot infer the element type of this comprehension
# A comprehension over the empty tuple never runs its body, so only where its list goes can type it
# (evens: list[int] = [c * 2 for c in ()], in iterate_tuples.py). Here nothing does, as for xs = [],
# and CPython prints [].
c = 1
xs = [c for c in ()]
print(xs)
