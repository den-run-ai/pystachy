# complex(str): complex_from_string_inner's forms, white space and parentheses, underscores
# between digits, Unicode digits and spaces, and its two ValueErrors
cases = ["1+2j", " ( 1.5-2j ) ", "j", "-j", "+J", "1_0+2_0j", "1__0", "nanj", "infj", "-INFINITYj",
         "1+", "", " ", "()", "(1", "1)", "1j)", "(1j", "1e5", "1e5j", "1e", "1e+j", "1.e-3j", ".5j",
         "+.5-.5J", "1+-2j", "1-+2j", "1+j", "1-j", "inf+nanj", "-nan-infj", "1_j", "_1", "1_",
         "0x10", "1 j", "1j ", "\t1\n", "1+2j+3", "--1", "+-1j", "1e1_0", "1_0e1_0j", "1.0_1",
         "١٢+٣j", " 1+1j ", "1é", "1+2j\x00", "1_2\x00", "NaN", "-0", "-0j",
         "(-0-0j)", "1e400", "-1e400j", "1e-400j", "infinityj", "infinj", "nanj_", "j1", "1jj"]
for s in cases:
    try:
        print(repr(s), complex(s))
    except ValueError as e:
        print(repr(s), "ValueError:", e)
