# error: expected int, got str (this list display's items have no one type: annotate the display with a union of their types where one holds them, or add '# pystachy: dynamic-any' before the module's code
# Items that no one type holds, nor a union the compiler infers (a list among scalars): the
# error names what holds them, an annotation or the module's dynamic Any opt-in
xs = [1, "two", [3]]
print(xs)
