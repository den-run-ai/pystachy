# Independent qualification review

Reviewed proposed tree `51f6c150748b2d17945e4d1c6779d8080b6edd6a` on base
`b0bda81ec2b9954c3c5e0f658c051439126a5c22`. All four source files match the
SHA-256 values and frozen copies in `frozen-repair.json`. This review changes no
source and did not duplicate the author's test executions.

No actionable correctness issue found in the four-file repair.

The initial full-census snapshot independently demonstrates the triggering shape:
`dynany_complex_decline.py` has `union_tags={float:1,bool:2}` while reflected complex
methods hold `union[bool,float,int]`. The method tests bool and float literals and
handles int in the final default arm. Requiring a materialized literal for every
member caused an adapter error before the existing proof model could inspect it.

The repair retains the complete abstract member domain and only decodes known
literal tags. It does not invent a missing tag number, discard the int member, or
silently assign unknown integers to the default member. This permits the final int
arm to be established by exclusion of known members. Source review confirms that
unknown literal constructions still refuse proof and unknown tests cannot introduce
member facts. The new negative controls exercise missing used mappings, unknown
tests, forced defaults, and unknown split-store/box constructions.

The report repair propagates nested function status `error` through both the
summary failure list and completion metadata. Rejected and explicitly unsupported
models remain reported as such; they are not converted into proofs. The canonical
output regression exercises generation and status validation, preventing a census
with uncounted adapter errors from claiming completion.

The retained focused-suite log records 49 passing tests. The independently captured
real snapshot is replayed by the author with 21/21 union reads, 21/21 payload
obligations and 4/4 removed checks proved. These bounded results do not replace the
pending fresh full-corpus census on the published repair commit. The historical
first census, its adapter errors and any inspection kills remain separate evidence.

The added complex-null residual is unrelated: its 12 rejected obligations stay
rejected and require the separately retained return/nullability-model disposition.
