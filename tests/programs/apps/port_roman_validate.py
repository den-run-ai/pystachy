# roman's fromRoman validates its argument with an anchored regular expression,
#     ^M{0,4}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$
# which the port replaces with a function (ports/roman/PORT.md): the alternations, the counts,
# `$` before a final newline (not before another line break), then every string of up to 4
# numeral letters
from roman import InvalidRomanNumeralError
from roman import fromRoman

cases = ["MCMXCIX", "MMMMCMXCIX", "MMMMDCCCLXXXVIII", "MDCLXVI", "CMXCIX", "CDXLIV", "mmxxiv",
         "Mi", "cccxxxiii", "MMMMM", "IIII", "VX", "IC", "MCMC", "CMCM", "DCCCC", "LXL", "XCX",
         "CDC", "IXI", "VIV", "IIIV", "DCD", "MCD", "CCCM", "XM", "IM", "VL", "LC", "DM",
         "MMMMMCM", "MDCLXVIX", "NN", "ABC", "%s", "M%dM", "M" * 50,
         "X\n", "\n", "X\n\n", "\nX", "X\r\n", "XC\n", "VIII\n", "mmxxiv\n", " X", "X ", "N ", "\t",
         "X\x00", "MCMXCIXM", "X\r", "X\x0b", "X\x0c", "X\x1c", "X\x85", "X\u2028",
         "\u216b", "X\u4e2d"]  # the last four: characters outside ASCII without a case
for s in cases:
    try:
        print(repr(s), fromRoman(s))
    except InvalidRomanNumeralError as e:
        print(repr(s), "InvalidRomanNumeralError:", repr(str(e)))

# every string of 1 to 4 letters over IVXLCDM: 7 + 49 + 343 + 2401 = 2800 strings
letters = "IVXLCDM"
count = 0
valid = 0
acc = 0
level = [""]
for depth in range(4):
    nxt: list[str] = []
    for p in level:
        for c in letters:
            nxt.append(p + c)
    level = nxt
    for s in level:
        count += 1
        try:
            v = fromRoman(s)
            valid += 1
            acc += v * count
        except InvalidRomanNumeralError:
            pass
print("checked", count, "valid", valid, "acc", acc)
