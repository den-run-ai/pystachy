# A capital sigma lowers to the final form after a cased letter where no cased letter follows,
# case-ignorable characters aside (Unicode's Final_Sigma, as CPython's lower() decides it), in
# every method that lowers: lower, title, capitalize and swapcase. casefold has no such rule.
def show(s: str) -> None:
    print(repr(s), repr(s.lower()), repr(s.title()), repr(s.capitalize()), repr(s.swapcase()), repr(s.casefold()),
          repr(s.upper()))


for s in ["Σ", "ΣΣ", "ΣΣΣ", "ΑΣ", "ΑΣΑ", "ΣΑ", "ΟΔΟΣ", "ΟΔΟΣ ΟΔΟΣ", "ΟΔΟΣ.", "ΟΔΟΣ:Α", "ΑΣ ΣΑ", "aΣ", "AΣb", "1Σ", "Σ1",
          " Σ", "Σ ", "Α'Σ", "ΑΣ'", "ΑΣ'Α", "Α'Σ'Α", "Α''Σ''", "'Σ", "Σ'", ".Σ", "Α.Σ.", "ΆΣ", "ΑΣ́",
          "ΑΣ́Α", "́Σ", "ʰΣ", "ΑʰΣ", "ΑΣʰ", "ΑΣʰ1", "ǅΣ", "ΑΣǅ", "界Σ", "Α界Σ", "ΑΣ界", "éΣ", "ΑΣé",
          "Α­Σ­", "Α​Σ", "ΑΣ\ud800", "\ud800Σ", "ς", "σ", "ΑΣσ", "ςΣ", "Α" + "'" * 300 + "Σ" + "." * 300,
          "Α" + "'" * 300 + "Σ" + "." * 300 + "Β", "Σ" * 257, "ΑΣ" * 129]:
    show(s)
