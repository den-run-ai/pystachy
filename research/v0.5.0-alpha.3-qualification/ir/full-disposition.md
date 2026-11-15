# Independent full IR disposition: alpha.2 → alpha.3

Baseline `80490143498d149d407343ba1cb7aedb1db2d2c5` → candidate `b0bda81ec2b9954c3c5e0f658c051439126a5c22`, tree `e027b37c888326e3d8a3e8b89522a6b397dcb86d`.

**All 562 changed records are explained; zero new rejections, unexpected process statuses or unexplained IR cases were found.** The retained 4,771-case scan has 4,209 unchanged cases. The strict comparator's differences remain intact and its exit 1 is accounted for by the explicit dispositions below.

| Changed record | Cases | Review |
| --- | ---: | --- |
| Accepted by both, changed IR | 379 | `accepted-ir-review.json` |
| Newly accepted | 121 | `acceptance-diagnostic-review.json` |
| Rejected by both, changed diagnostic | 62 | `acceptance-diagnostic-review.json` |
| New rejection | 0 | Full retained status census |

## Main conclusions

- Of the 379 accepted IR changes, 196 are exact checkout-path literals with identical referenced library bytes, and 32 affect only unreferenced class declarations. The remaining 151 receive explicit per-case semantic dispositions and retain complete changed-function/global inventories.
- The principal semantic changes are the scanned VTuple identity header and numeric identity companions, numeric generator promise companions, fixed-constructor admission, enum comparison/payload repair, lazy uncalled reflected-method generation, and retained None guards on Tomllib Output.flags receivers before method calls. No general normalization of instructions, constants, branches, addresses or diagnostics was used to accept them.
- Prior enum-only review is bound by whole IR equality case by case. Twenty-two broad old/new pairs are exact prior pairs after validated checkout literals; four additional broad-baseline deltas were separately reviewed. That older review is not substituted for the release-wide audit.
- The 121 new acceptances comprise 120 added inputs and the changed upstream_setcomps input. There are 119 positive fixtures and two explicitly documented deviation fixtures. All 62 changed rejections keep exit 1, exactly one expected diagnostic and no LLVM output; no error fixture became accepted.
- An independent original-input supplement compiles 13 old-source cases, including six removed error inputs, five modified inputs (one an import helper), the renamed reflected_rand input, and its import consumer. All 129 original source/sidecar/helper hashes and retained results were verified. It records five cases accepted by both, three rejected by both and five newly accepted, with zero new rejections. The renamed file differs only in its first comment and has the same AST; it was not falsely called byte-identical.

## Approval scope

This independent review finds no blocking source/IR defect in the retained candidate comparison. It grants **no native runtime, GC, performance, bootstrap or Lean proof**. Those gates remain separate. In particular, concurrently discovered dynamic-complex Lean adapter errors and residual obligations are not waived; any repair must be separately pinned, reviewed and validated.

`full-disposition.json` has one unique entry for each of all 562 changed cases, with component review pointers and retained result hashes. The accepted-case source and old/new IR hashes and all acceptance/diagnostic evidence were rechecked during final assembly. Raw oracle output and production source remain untouched.
