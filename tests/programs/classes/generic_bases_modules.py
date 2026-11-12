# Generic classes of a hierarchy in imported modules: hiermods.tasks.Task[T] derives from
# hiermods.futs.Fut[T], which derives from hiermods.base.Base. Annotations name their
# specializations through the modules (tasks.Task[int], a subscript of a generic class whose
# base is another module's), and specializations whose type arguments are other
# specializations, Fut[Fut[int]] made in a function compiled late, are made again before the
# code that dispatches on Base compiles in the next pass.
from hiermods import base, futs, tasks


def wrap(v):
    return futs.Fut(v)


def show(b):
    print(b.kind(), b.name)


show(base.Base("b"))
inner = futs.Fut(1)
outer = wrap(inner)
t: tasks.Task[int] = tasks.Task(2, 3)
items: list[base.Base] = [inner, outer, t, tasks.Task("s", 1)]
for b in items:
    show(b)
print(outer.get().get() + t.get(), isinstance(outer, futs.Fut), isinstance(t, futs.Fut))
