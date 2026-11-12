"""The iterators that iter() makes of builtin containers, as classes of the subset.

Pystachy's own module, after the iterator types of CPython 3.13's Objects/listobject.c,
unicodeobject.c, tupleobject.c, dictobject.c, setobject.c and rangeobject.c: each __next__
gives the next item or raises StopIteration, and an exhausted iterator stays exhausted. The
compiler loads this module for a program that calls iter() (Loader.program); its classes are
not names a program can import. The __pys_* calls are compiler primitives: the runtime's
entry walk of a dict or set, which a for loop over one uses too.
"""


class list_iterator:
    # iter(xs) of a list: its items by index, reading the list's length at each step (a loop
    # sees items appended meanwhile); once exhausted it stays so, as CPython drops the list
    def __init__(self, xs):
        self._xs = xs
        self._i = 0

    def __iter__(self):
        return self

    def __next__(self):
        i = self._i
        xs = self._xs
        if i < len(xs):
            self._i = i + 1
            return xs[i]
        self._i = 1 << 62
        raise StopIteration


class tuple_iterator:
    # iter(t) of a tuple whose items share one type: a list of its items (which cannot change)
    def __init__(self, xs):
        self._xs = xs
        self._i = 0

    def __iter__(self):
        return self

    def __next__(self):
        i = self._i
        xs = self._xs
        if i < len(xs):
            self._i = i + 1
            return xs[i]
        raise StopIteration


class str_ascii_iterator:
    # iter(s) of a str: decode at a byte cursor, linear also for non-ASCII strings.
    def __init__(self, s):
        self._s = s
        self._i = 0

    def __iter__(self):
        return self

    def __next__(self):
        i = self._i
        s = self._s
        if i < __pys_text_size(s):
            self._i = __pys_text_next(s, i)
            return __pys_text_at(s, i)
        raise StopIteration


class range_iterator:
    # iter(range(start, stop, step)): its n items from start
    def __init__(self, start, step, n):
        self._next = start
        self._step = step
        self._n = n

    def __iter__(self):
        return self

    def __next__(self):
        # pys_range_len stores an unsigned count in an i64. Zero alone means exhaustion;
        # crossing the sign bit must wrap explicitly because signed subtraction checks overflow.
        if self._n != 0:
            v = self._next
            self._n = 9223372036854775807 if self._n == -9223372036854775807 - 1 else self._n - 1
            if self._n != 0:
                self._next = v + self._step
            return v
        raise StopIteration


class dict_keyiterator:
    # iter(d), iter(d.keys()): the keys by entry, failing if the dict changes size (or, at the
    # same size, gives more keys than it had); once exhausted or failed, it stays so
    def __init__(self, d):
        self._d = d
        self._used = len(d)
        self._at = 0
        self._count = 0
        self._live = True

    def __iter__(self):
        return self

    def __next__(self):
        d = self._d
        if self._used < 0 or (self._live and len(d) != self._used):
            self._used = -1  # (as CPython's does: it fails again at each call)
            raise RuntimeError("dictionary changed size during iteration")
        if not self._live:
            raise StopIteration
        j = __pys_dict_next(d, self._at, self._used, -1)
        if j < 0:
            self._live = False
            raise StopIteration
        if self._count >= self._used:
            self._live = False
            raise RuntimeError("dictionary keys changed during iteration")
        self._at = j + 1
        self._count += 1
        return __pys_dict_key(d, j)


class dict_valueiterator:
    # iter(d.values()): the values by entry, as dict_keyiterator walks the keys
    def __init__(self, d):
        self._d = d
        self._used = len(d)
        self._at = 0
        self._count = 0
        self._live = True

    def __iter__(self):
        return self

    def __next__(self):
        d = self._d
        if self._used < 0 or (self._live and len(d) != self._used):
            self._used = -1  # (as CPython's does: it fails again at each call)
            raise RuntimeError("dictionary changed size during iteration")
        if not self._live:
            raise StopIteration
        j = __pys_dict_next(d, self._at, self._used, -1)
        if j < 0:
            self._live = False
            raise StopIteration
        if self._count >= self._used:
            self._live = False
            raise RuntimeError("dictionary keys changed during iteration")
        self._at = j + 1
        self._count += 1
        return __pys_dict_val(d, j)


class dict_itemiterator:
    # iter(d.items()): (key, value) by entry, as dict_keyiterator walks the keys
    def __init__(self, d):
        self._d = d
        self._used = len(d)
        self._at = 0
        self._count = 0
        self._live = True

    def __iter__(self):
        return self

    def __next__(self):
        d = self._d
        if self._used < 0 or (self._live and len(d) != self._used):
            self._used = -1  # (as CPython's does: it fails again at each call)
            raise RuntimeError("dictionary changed size during iteration")
        if not self._live:
            raise StopIteration
        j = __pys_dict_next(d, self._at, self._used, -1)
        if j < 0:
            self._live = False
            raise StopIteration
        if self._count >= self._used:
            self._live = False
            raise RuntimeError("dictionary keys changed during iteration")
        self._at = j + 1
        self._count += 1
        return (__pys_dict_key(d, j), __pys_dict_val(d, j))


class set_iterator:
    # iter(s) of a set or frozenset: its elements by slot, failing if the set changes size
    def __init__(self, s):
        self._s = s
        self._used = len(s)
        self._at = 0
        self._live = True

    def __iter__(self):
        return self

    def __next__(self):
        s = self._s
        if self._used < 0 or (self._live and len(s) != self._used):
            self._used = -1  # (as CPython's does: it fails again at each call)
            raise RuntimeError("Set changed size during iteration")
        if not self._live:
            raise StopIteration
        j = __pys_set_next(s, self._at, self._used)
        if j < 0:
            self._live = False
            raise StopIteration
        self._at = j + 1
        return __pys_set_key(s, j)


class enumerate_iterator:
    # The source is already an iterator; construction never asks it for an item.
    def __init__(self, it, start):
        self._it = it
        self._index = start

    def __iter__(self):
        return self

    def __next__(self):
        item = next(self._it)
        index = self._index
        self._index = index + 1
        return (index, item)


class zip_iterator:
    # A statically typed tuple holds each iterator, including heterogeneous ones.
    def __init__(self, iters):
        self._iters = iters

    def __iter__(self):
        return self

    def __next__(self):
        return __pys_iter_nexts(self._iters)


class map_iterator:
    def __init__(self, fn, iters):
        self._fn = fn
        self._iters = iters

    def __iter__(self):
        return self

    def __next__(self):
        return __pys_iter_apply(self._fn, self._iters)


class filter_iterator:
    def __init__(self, fn, it):
        self._fn = fn
        self._it = it

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            item = next(self._it)
            if self._fn(item):
                return item


class filter_truth_iterator:
    def __init__(self, it):
        self._it = it

    def __iter__(self):
        return self

    def __next__(self):
        while True:
            item = next(self._it)
            if item:
                return item


class reversed_iterator:
    # A list's original last index, but its current contents on each step.
    def __init__(self, xs):
        self._xs = xs
        self._index = len(xs) - 1

    def __iter__(self):
        return self

    def __next__(self):
        index = self._index
        if index >= 0 and index < len(self._xs):
            self._index = index - 1
            return self._xs[index]
        self._index = -1
        raise StopIteration


class reversed_str_iterator:
    # Use a byte cursor so reversing a Unicode string stays linear.
    def __init__(self, s):
        self._s = s
        self._at: int = __pys_text_size(s)

    def __iter__(self):
        return self

    def __next__(self):
        if self._at > 0:
            self._at = __pys_text_prev(self._s, self._at)
            return __pys_text_at(self._s, self._at)
        raise StopIteration


class reversed_range_iterator:
    def __init__(self, start, step, count):
        self._start = start
        self._step = step
        self._count = count

    def __iter__(self):
        return self

    def __next__(self):
        if self._count != 0:
            self._count = 9223372036854775807 if self._count == -9223372036854775807 - 1 else self._count - 1
            return __pys_iter_range_at(self._start, self._step, self._count)
        raise StopIteration


class list_reverseiterator:
    def __init__(self, xs):
        self._xs = xs
        self._index = len(xs) - 1

    def __iter__(self):
        return self

    def __next__(self):
        index = self._index
        if index >= 0 and index < len(self._xs):
            self._index = index - 1
            return self._xs[index]
        self._index = -1
        raise StopIteration


class dict_reversekeyiterator:
    def __init__(self, d):
        self._d = d
        self._used = len(d)
        self._at: int = __pys_dict_end(d) - 1
        self._live = True

    def __iter__(self):
        return self

    def __next__(self):
        d = self._d
        if self._used < 0 or (self._live and len(d) != self._used):
            self._used = -1
            raise RuntimeError("dictionary changed size during iteration")
        if not self._live:
            raise StopIteration
        j = __pys_dict_prev(d, self._at, self._used, -1)
        if j < 0:
            self._live = False
            raise StopIteration
        self._at = j - 1
        return __pys_dict_key(d, j)


class bytes_iterator:
    def __init__(self, xs):
        self._xs = xs
        self._index = 0

    def __iter__(self):
        return self

    def __next__(self):
        index = self._index
        if index < len(self._xs):
            self._index = index + 1
            return self._xs[index]
        raise StopIteration
