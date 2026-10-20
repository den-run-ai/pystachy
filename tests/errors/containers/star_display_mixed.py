# error: star_display_mixed.py:3: error: items of types int and str in one display need an annotation where it goes (list[int | str])
a = [1]
print([*a, "s"])
