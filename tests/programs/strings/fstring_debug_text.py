# The text a self-documenting f-string field prints, as CPython 3.13's tokenizer gives it: the
# expression as written, without its comments, which it finds by tracking quotes one at a time;
# so a '#' after a quote in a triple-quoted string, or in a nested f-string that reuses its quote,
# starts one (and the rest, '=' too, is left out)
x = "a'#"
d = {"#": 1}
print(f"{x=}|{'#'=}|{"#"=}|{d["#"]=}|{'\'#'=}|{"a" + '"#'=}|{'''#'''=}|{"""a#b"""=}")
print(f"{x # a comment, with ' and "
=}|{x  # c
 = !r:>8}|{f'{"#"}'=}|{f'{x!r:#>9}'=}")
print(f"{'''a'#'''=}")
print(f"{f'{'#'}'=}")
print(f"""{f'''{x # c
}'''=}""")
print(f"""{x =\
}|{x \
= \
!r:>8}""")
print(f"{'\\'+'#'=}|{"\\" '#' = }")
