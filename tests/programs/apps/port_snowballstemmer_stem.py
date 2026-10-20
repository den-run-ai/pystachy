# snowballstemmer's English (Porter2) and Porter stemmers (ports/snowballstemmer): 384 English
# words, chosen for the suffixes each step of the two algorithms removes or rewrites, each with
# its Porter2 stem and its Porter stem (WORDS: "word porter2 porter", as the upstream package
# stems them under CPython; the program prints any word that stems otherwise), then edge cases:
# empty and short words, apostrophes, y and Y, Porter2's exception lists and special prefixes,
# input the algorithms do not expect (capitals, digits, spaces), a long word, the rest of the
# stemmer API, and pseudo-random words, with one object of each stemmer for every word in turn.
import snowballstemmer
from snowballstemmer.english_stemmer import EnglishStemmer
from snowballstemmer.porter_stemmer import PorterStemmer

WORDS = [
    # plurals (step 1a)
    "caresses caress caress", "ponies poni poni", "ties tie ti", "caress caress caress",
    "cats cat cat", "gas gas ga", "this this thi", "kiwis kiwi kiwi", "classes class class",
    "dresses dress dress", "buses buse buse", "bosses boss boss", "flies fli fli", "cries cri cri",
    "berries berri berri", "babies babi babi", "ladies ladi ladi", "toys toy toi", "days day dai",
    "keys key kei", "monkeys monkey monkei", "species speci speci", "series seri seri",
    "physics physic physic", "politics polit polit", "analysis analysi analysi",
    # -eed, -ed, -ing and their adverbs (step 1b)
    "feed feed feed", "agreed agre agre", "disagreed disagre disagre",
    "guaranteed guarante guarante", "plastered plaster plaster", "bled bled bled",
    "motoring motor motor", "sing sing sing", "conflated conflat conflat",
    "troubled troubl troubl", "sized size size", "hopping hop hop", "tanned tan tan",
    "falling fall fall", "hissing hiss hiss", "fizzed fizz fizz", "failing fail fail",
    "filing file file", "hoped hope hope", "hoping hope hope", "hopped hop hop",
    "controlled control control", "rolling roll roll", "stopped stop stop", "planned plan plan",
    "jumped jump jump", "walked walk walk", "talking talk talk", "believed believ believ",
    "created creat creat", "decided decid decid", "dated date date", "saying say sai",
    "sitting sit sit", "getting get get", "swimming swim swim", "running run run",
    "eating eat eat", "writing write write", "playing play plai", "studying studi studi",
    "crying cri cry", "dying die dy", "lying lie ly", "tying tie ty", "flying fli fly",
    "trying tri try", "enjoyed enjoy enjoi", "carried carri carri", "worried worri worri",
    "hurried hurri hurri", "admittedly admit admittedli", "reportedly report reportedli",
    "exceedingly exceed exceedingli", "amazingly amaz amazingli", "knowingly know knowingli",
    "seemingly seem seemingli", "hated hate hate", "bored bore bore", "freed freed freed",
    "speeding speed speed", "needed need need", "breeding breed breed",
    # -y (step 1c)
    "happy happi happi", "sky sky sky", "happily happili happili", "easily easili easili",
    "fairly fair fairli", "generously generous gener", "quickly quick quickli",
    "beautifully beauti beautifulli", "truly truli truli", "family famili famili",
    "history histori histori", "study studi studi", "story stori stori", "city citi citi",
    "country countri countri", "enemy enemi enemi", "mystery mysteri mysteri", "deny deni deni",
    "apply appli appli", "by by by", "say say sai", "cry cri cry", "dry dri dry",
    # step 2
    "relational relat relat", "conditional condit condit", "rational ration ration",
    "valency valenc valenc", "hesitancy hesit hesit", "digitizer digit digit",
    "conformably conform conform", "radically radic radic", "differently differ differ",
    "vilely vile vile", "analogously analog analog", "vietnamization vietnam vietnam",
    "predication predic predic", "operator oper oper", "feudalism feudal feudal",
    "decisiveness decis decis", "hopefulness hope hope", "callousness callous callous",
    "formality formal formal", "sensitivity sensit sensit", "sensibility sensibl sensibl",
    "organization organiz organ", "civilization civil civil", "national nation nation",
    "international internat intern", "traditional tradit tradit", "emotional emot emot",
    "professional profession profession", "generalization general gener",
    "modernization modern modern", "authorization author author", "visualization visual visual",
    "criticism critic critic", "realism realism realism", "tourism tourism tourism",
    "effectiveness effect effect", "attractiveness attract attract", "carefulness care care",
    "usefulness use us", "nervousness nervous nervous", "seriousness serious serious",
    "consciousness conscious conscious", "generosity generos generos", "curiosity curios curios",
    "activity activ activ", "creativity creativ creativ", "productivity product product",
    "possibility possibl possibl", "responsibility respons respons", "flexibility flexibl flexibl",
    "visibility visibl visibl", "probability probabl probabl", "biology biolog biologi",
    "geology geolog geologi", "technology technolog technologi", "apology apolog apologi",
    "logically logic logic", "fearlessly fearless fearlessli", "carelessly careless carelessli",
    "abundantly abund abundantli", "fluently fluentli fluentli", "entirely entir entir",
    "obviously obvious obvious", "noble nobl nobl", "nobly nobli nobli",
    # step 3
    "triplicate triplic triplic", "formative format form", "formalize formal formal",
    "electricity electr electr", "electrical electr electr", "hopeful hope hope",
    "goodness good good", "duplicate duplic duplic", "communicate communic commun",
    "indicate indic indic", "authenticate authent authent", "demonstrative demonstr demonstr",
    "informative inform inform", "talkative talkat talk", "normalize normal normal",
    "finalize final final", "specialize special special", "realize realiz realiz",
    "classical classic classic", "physical physic physic", "musical music music",
    "practical practic practic", "critical critic critic", "mechanical mechan mechan",
    "magical magic magic", "cheerful cheer cheer", "careful care care", "peaceful peac peac",
    "wonderful wonder wonder", "powerful power power", "kindness kind kind", "darkness dark dark",
    "happiness happi happi", "sadness sad sad", "weakness weak weak", "illness ill ill",
    "authenticity authent authent", "publicity public public",
    # step 4
    "revival reviv reviv", "allowance allow allow", "inference infer infer",
    "airliner airlin airlin", "gyroscopic gyroscop gyroscop", "adjustable adjust adjust",
    "defensible defens defens", "irritant irrit irrit", "replacement replac replac",
    "adjustment adjust adjust", "dependent depend depend", "adoption adopt adopt",
    "communism communism commun", "activate activ activ", "angularity angular angular",
    "homologous homolog homolog", "effective effect effect", "bowdlerize bowdler bowdler",
    "arrival arriv arriv", "approval approv approv", "survival surviv surviv",
    "importance import import", "appearance appear appear", "performance perform perform",
    "resistance resist resist", "difference differ differ", "independence independ independ",
    "existence exist exist", "conference confer confer", "reference refer refer",
    "teacher teacher teacher", "worker worker worker", "player player player",
    "computer comput comput", "heroic heroic heroic", "poetic poetic poetic",
    "dramatic dramat dramat", "scientific scientif scientif", "comfortable comfort comfort",
    "reasonable reason reason", "available avail avail", "valuable valuabl valuabl",
    "possible possibl possibl", "visible visibl visibl", "terrible terribl terribl",
    "important import import", "assistant assist assist", "significant signific signific",
    "elegant eleg eleg", "agreement agreement agreement", "management manag manag",
    "development develop develop", "government govern govern", "movement movement movement",
    "payment payment payment", "statement statement statement", "treatment treatment treatment",
    "different differ differ", "excellent excel excel", "efficient effici effici",
    "patient patient patient", "student student student", "nation nation nation",
    "action action action", "education educ educ", "information inform inform",
    "decision decis decis", "revision revis revis", "tension tension tension",
    "ambition ambit ambit", "separate separ separ", "celebrate celebr celebr", "operate oper oper",
    "motivate motiv motiv", "absurdity absurd absurd", "quality qualiti qualiti",
    "reality realiti realiti", "famous famous famou", "dangerous danger danger",
    "various various variou", "active activ activ", "massive massiv massiv",
    "expensive expens expens", "positive posit posit", "organize organiz organ",
    "recognize recogn recogn", "apologize apolog apolog",
    # step 5
    "probate probat probat", "rate rate rate", "cease ceas ceas", "controll control control",
    "roll roll roll", "generate generat gener", "debate debat debat", "complete complet complet",
    "cone cone cone", "allele allel allel", "wrestle wrestl wrestl", "little littl littl",
    "bottle bottl bottl", "fall fall fall", "skill skill skill", "spell spell spell",
    "well well well",
    # whole families
    "connect connect connect", "connection connect connect", "connections connect connect",
    "connective connect connect", "connected connect connect", "connecting connect connect",
    "consign consign consign", "consigned consign consign", "consigning consign consign",
    "consignment consign consign", "consistency consist consist", "consistently consist consist",
    "knight knight knight", "knightly knight knightli", "knights knight knight",
    "knightliness knightli knightli", "generation generat gener", "generations generat gener",
    "generic generic gener", "argue argu argu", "argued argu argu", "argues argu argu",
    "arguing argu argu", "argus argus argu", "argument argument argument",
    "arguments argument argument",
    # rules and table entries the words above leave untested: Porter2 keeps a double letter
    # after a, e or o that begins the word (adding), the doubles bb, dd, ff and rr, -ogist,
    # step 3's -tional and -ational, -ion after a letter other than s or t, a y after a first
    # letter that is not a vowel (dyed), the prefix later, the exception evening, and words
    # that only begin as an exception does (however, newsgroups)
    "adding add ad", "added add ad", "ebbing ebb eb", "egged egg eg", "offing off of",
    "padding pad pad", "rubbing rub rub", "stuffed stuf stuf", "stirred stir stir",
    "beginning begin begin", "winning win win", "accelerated acceler acceler",
    "capitalized capit capit", "organizing organiz organ", "dyed dy dy",
    "vacancy vacanc vacanc", "probably probabl probabl", "actually actual actual",
    "currently current current", "personality person person", "conventional convent convent",
    "federalism feder feder", "initializer initi initi", "accumulator accumul accumul",
    "biologist biolog biologist", "geologists geolog geologist", "laterally lateral later",
    "additionally addit addition", "functionality function function",
    "operationally oper operation", "educationally educ education", "eligible elig elig",
    "disagreement disagr disagr", "opinion opinion opinion", "companion companion companion",
    "criterion criterion criterion", "evening evening even", "however howev howev",
    "newsgroups newsgroup newsgroup",
]

CASES = [
    # empty and short words
    "", "a", "is", "as", "by", "at", "on", "us", "ss", "s", "e", "u", "i", "x", "ed", "ing",
    "ly", "ies", "sses", "eed", "eedly", "ingly", "ied", "tied", "cries", "die", "dies", "lie",
    "lies", "bli", "ogi", "li", "tional", "ational", "ization", "fulness", "alism", "iviti",
    # apostrophes: Porter2 drops a leading one and the 's endings
    "'quoted'", "dog's", "dogs'", "'", "''", "'''s", "'s'", "'s", "''s'", "o'clock", "can't",
    "won't", "it's", "rock'n'roll",
    # y and Y: Porter2 marks a consonant y as Y, and the original Porter algorithm does not
    "Yay", "y", "Y", "yy", "yyy", "Yyyy", "ay", "aye", "sayyid", "eyy", "yes", "toy", "toying",
    "boyish", "employ", "employing", "obeying", "yelling", "sayings", "youth", "royalty",
    # Porter2's exceptions, and the prefixes it gives a region of their own
    "skis", "skies", "sky", "idly", "gently", "ugly", "early", "only", "singly", "news", "howe",
    "atlas", "cosmos", "bias", "andes", "inning", "innings", "outing", "canning", "herring",
    "earring", "proceed", "exceed", "succeed", "proceeding", "exceedingly", "reproceed", "gener",
    "general", "generate", "commun", "community", "arsenal", "arsen", "emerge", "emergency",
    "inter", "interest", "past", "pasted", "universe", "universal", "universities",
    # input the algorithms do not expect: they want lower-case letters
    "1990s", "a1b2c3ing", "co-op", "re-entering", "ABCDEFING", "RUNNING", "Running", "\t", " ",
    "a b", "word\nnewline", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaing",
]


def lcg_words(n: int, seed: int) -> list[str]:
    # words of 1 to 9 letters (and apostrophes) and one of 20 endings, from a linear
    # congruential generator, so that CPython and Pystachy stem the same words
    alpha = "aeiouybcdfghjklmnprstvwxz'"
    endings = ["", "s", "ing", "ed", "ly", "ness", "ational", "ization", "fulness", "iveness",
               "iciti", "ement", "able", "ies", "eed", "y", "'s", "est", "er", "ism"]
    words: list[str] = []
    x = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        w = ""
        for j in range(1 + x % 9):
            x = (x * 1103515245 + 12345) % 2147483648
            w += alpha[(x >> 8) % len(alpha)]
        x = (x * 1103515245 + 12345) % 2147483648
        words.append(w + endings[(x >> 10) % len(endings)])
    return words


def main() -> None:
    english = EnglishStemmer()
    porter = PorterStemmer()
    differ = 0
    for entry in WORDS:
        parts = entry.split()
        word = parts[0]
        stem2 = english.stemWord(word)
        stem1 = porter.stemWord(word)
        if stem2 != parts[1] or stem1 != parts[2]:
            print("stems differ from the table:", word, stem2, stem1)
            differ += 1
    print(len(WORDS), "words,", differ, "stemmed otherwise")
    sentence = "the runners were running faster than the other runners ran".split()
    print(english.stemWords(sentence))
    print(porter.stemWords(sentence))

    for word in CASES:
        print(repr(word), repr(english.stemWord(word)), repr(porter.stemWord(word)))

    # a long word, then a short one with the same objects
    long = "nationalization" * 200 + "ing"
    a = english.stemWord(long)
    b = porter.stemWord(long)
    print(len(long), len(a), len(b), a[-20:], b[-20:])
    print(english.stemWord("a"), porter.stemWord("a"))

    # algorithms() (which lists all 36 upstream), stemWords, and the cursor API the generated
    # code is written against
    print([name in snowballstemmer.algorithms() for name in ["english", "porter"]])
    print(english.stemWords([]), porter.stemWords([""]))
    print(english.stemWords("we are the world".split()))
    english.set_current("hopefulness")
    print(english.get_current(), english.cursor, english.limit, english.limit_backward)
    english.bra = 4
    english.ket = 7
    print(english.slice_to(), english.assign_to())
    english.slice_from("e")
    print(english.get_current(), english.bra, english.ket, english.limit)
    other = PorterStemmer()
    other.set_current("other")
    porter.copy_from(other)
    porter.insert(0, 0, "an")
    print(porter.get_current(), porter.bra, porter.ket, porter.limit, other.get_current())

    # UTF-8 passes through: these words come out as CPython's (PORT.md lists ones that do not)
    for word in ["naïvely", "cafés", "résumés", "jalapeños", "über", "日本"]:
        print(word, english.stemWord(word), porter.stemWord(word))

    words = lcg_words(300, 42)
    line: list[str] = []
    for word in words:
        line.append(word + ":" + english.stemWord(word) + ":" + porter.stemWord(word))
        if len(line) == 6:
            print(" ".join(line))
            line = []
    print(len(words), "pseudo-random words")


main()
