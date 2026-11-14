"""Record the reviewed explanation of every assigned IR change."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
rows = json.loads((ROOT / "constructor-review-cases.json").read_text())
mechanical = {row["number"]: row for row in json.loads((ROOT / "constructor-mechanical.json").read_text())}

notes = {
    85: "Sqids' 358-element string VTuple allocates 2,880 rather than 2,872 bytes; all item offsets and iteration loads advance by one word for the identity-companion header. Element values and branch logic are unchanged.",
    86: "Sqids' 358-element string VTuple allocates 2,880 rather than 2,872 bytes; all item offsets and iteration loads advance by one word for the identity-companion header. Element values and branch logic are unchanged.",
    110: "Class field-name metadata uses runtime-length tuples: the empty tuple is 16 rather than 8 bytes, and the two-name tuple is 32 rather than 24 bytes with item offsets 2/3 rather than 1/2.",
    140: "Used keeps one nominal i64 layout while its list and tuple constructors specialize separately. The unused fixed-field class gains only a declaration; unused invalid constructors/methods are still absent. Method bodies agree after demonstrated symbol renaming. Nominal allocation moves before argument-container construction, as in the existing nominal-class path; argument expressions and __init__ calls retain their order.",
    144: "Imported Count keeps one nominal i64 layout and separate list/tuple constructor specializations; count/read no longer need class-template suffixes. The unused sibling gains only its fixed layout. Functions agree after class/method and content-derived string renaming, except for nominal allocation before argument-container construction.",
    146: "Only LoopEarlier and TryEarlier have annotations established before field stores; their unchanged field layouts become nominal. LoopLater and TryLater remain class templates. Every function body agrees after the demonstrated class-name mapping.",
    147: "AnnotatedFirst retains its one i64 nominal layout and specializes constructor code. AnnotatedSecond remains two distinct i64/pointer template layouts because its first stores precede the annotation. Every function body agrees after the demonstrated class-name mapping.",
    148: "Earlier and Declared retain one nominal i64 layout; Later remains a class template because its first store precedes the annotation. Every function body agrees after the demonstrated class-name mapping.",
    149: "Converted and Checked retain their fixed pointer/i64 layouts while their integer/string constructor code specializes independently. Nonconstructor get/show functions become ordinary nominal methods/functions. Every function body agrees after demonstrated class/method renaming and content-derived string resolution.",
    975: "Both string and float VTuples gain the extra identity-companion header word. The float tuple additionally records its two existing constant-float Dyn identities through pys_vtuple_set_identity(kind=2); class field storage and union comparisons are unchanged.",
    1162: "The dormant peer's two-string VTuple gains one header word: 32 versus 24 bytes and item offsets 2/3 versus 1/2. This does not turn on scalar identity tracking for the dormant native integer list.",
    1586: "io.IncrementalNewlineDecoder keeps its existing {i1,i1,i64} layout as a nominal class. Constructor/decode code may specialize, while the newlines property has one ordinary method. All 48 function bodies agree after demonstrated symbol mapping and full-content string/TBAA reference resolution; apparent changes in other io functions are only renumbered references.",
    1588: "io.IncrementalNewlineDecoder retains one {i1,i1,i64} layout and specialized constructors/decode methods; show/getstate/setstate/reset/newlines become ordinary nominal methods. All bodies agree under demonstrated symbol/content mapping except main.init, where raw nominal allocation precedes the existing translation-argument load. No user call moves across another user call.",
    1593: "io.IncrementalNewlineDecoder's unchanged {i1,i1,i64} layout and constructor gain canonical nominal names. All 42 function bodies agree after the demonstrated class-name mapping; reflected source module/name strings remain unchanged.",
    2114: "Runtime tuples passed to the alias-annotated dotted helper gain one header word: three strings allocate 40 instead of 32 bytes, empty tuples allocate 16 instead of 8, and element offsets increase by one. Alias annotation behavior is unchanged.",
    2117: "The runtime three-string tuple passed through imported aliases gains one header word and shifts item offsets by one; imported-alias resolution and values are unchanged. Shared test-module ImportError path payloads remain verbatim identical.",
    2319: "The kwargs-holding class C retains its pointer layout as a nominal class while __init__/meth still specialize argument packs. All methods agree after class-name mapping; its test caller uses the existing nominal allocation-before-pack path. Keyword insertion order and the constructor/method call sequence remain unchanged.",
    2540: "io.IncrementalNewlineDecoder uses the canonical nominal layout/name. Its existing unsupported-object constructor still raises the same exception; raw outer allocation moves before constructing the Latin1 argument, but Latin1.__init__ still executes before the decoder __init__. No callback is invoked by GC collection itself.",
    2541: "io.IncrementalNewlineDecoder retains its {i1,i1,i64} nominal layout, and newlines becomes an ordinary property method. All nine function bodies agree after demonstrated symbol mapping and full-content string/TBAA resolution; the documented tuple-decoder limitation remains unchanged.",
}

result = []
for row in rows:
    number = row["number"]
    if row["declarations_only"]:
        causes = ["fixed_layout_declaration"]
        names = [line.split(" = type ")[0] for line in row["declarations"]]
        reason = ("Only fixed nominal LLVM class declarations are added: " + ", ".join(names) +
                  ". No function, global value, instruction or runtime call changes; unused method bodies remain absent.")
    else:
        reason = notes[number]
        causes = (["vtuple_identity_layout"] if number in (85, 86, 110, 975, 1162, 2114, 2117)
                  else ["fixed_layout_constructor_specialization"])
        if number == 975:
            causes.append("tuple_numeric_identity")
    item = {"number": number, "case": row["case"], "causes": causes,
            "rationale": reason, "unexpected": False,
            "evidence": [row["directory"] + "/ir.location-normalized.diff"]}
    if number in mechanical:
        item["mechanical_support"] = mechanical[number]
    result.append(item)
assert len(result) == 43
(ROOT / "constructor-semantic-review.json").write_text(json.dumps(result, indent=2) + "\n")
print("Reviewed", len(result), "assigned IR cases")
