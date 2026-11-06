# Published measurement revisions

Raw measurement records retain the local Git commit IDs captured during the work.
Publication through the connected GitHub integration recreated commit metadata,
so the public commit IDs differ. **Every mapped commit has the identical Git tree
as its local checkpoint.** File blobs and trees were checked by Git object hash
before the branch was updated. Use the public IDs when checking out a measured
snapshot; the original records have not been rewritten.

| Local checkpoint | Public commit with identical tree | Purpose |
|---|---|---|
| `79b86a85f374` | [`f631998b4fbe`](https://github.com/den-run-ai/pystachy/commit/f631998b4fbea5fe98a90e31388e1d4dec84c2c0) | Keep receiver typing overlay native-compilable |
| `9eaf428296a0` | [`c1f8c82a9156`](https://github.com/den-run-ai/pystachy/commit/c1f8c82a91566220dd4ed84b5f1d49e0fed8d0e4) | Bound LLVM worker lifetimes and expose optimization tiers |
| `061d309c13c7` | [`a444e5aa260c`](https://github.com/den-run-ai/pystachy/commit/a444e5aa260cb73ca03caa1814f5a7c849d3a5e6) | Compare temporary bootstrap and LLVM optimization policies |
| `ba5c96a1b526` | [`f6c6ba2b3504`](https://github.com/den-run-ai/pystachy/commit/f6c6ba2b3504fa2ad1687ab3f9d8f4521495e1b5) | Detect allocator declarations without matching IR strings |
| `4c96a6a0f459` | [`8ad4fb3ab4d9`](https://github.com/den-run-ai/pystachy/commit/8ad4fb3ab4d9c0d43a5f4d597aeb4eda727f0fb7) | Compare complete split bootstraps with bounded cleanup |
| `9ba9e0b8fa81` | [`b6987d77a203`](https://github.com/den-run-ai/pystachy/commit/b6987d77a203db514d28ae9f845481ef83a12650) | Keep ordinary final compiler equality in mixed bootstrap sweeps |
| `64014f16d96f` | [`ba55727ad6b2`](https://github.com/den-run-ai/pystachy/commit/ba55727ad6b20ccdcac2b7e0c7840ed27c88042c) | Verify native receiver overlay with frozen IR witnesses |
| `91abd72482a4` | [`e6f63907973a`](https://github.com/den-run-ai/pystachy/commit/e6f63907973ac2fae94fe6cd10b71927b3115d5f) | Use portable static and runtime receiver bindings |
| `c20ed941d559` | [`aae5a6a1bcb2`](https://github.com/den-run-ai/pystachy/commit/aae5a6a1bcb26a2481e3d83fc51769e21d94223a) | Record portable receiver host validation and timings |
| `d137616584b0` | [`8bd7fc00db80`](https://github.com/den-run-ai/pystachy/commit/8bd7fc00db803e426e516713d9f50465df61826a) | Keep allocator declaration recognition behind LLVM lowering |
| `384310d07539` | [`ae127e0cf09c`](https://github.com/den-run-ai/pystachy/commit/ae127e0cf09c437115fba4acff04f5d9c450495a) | Record full bootstrap gains and reviewed compiler validation |

[Machine-readable full commit and tree identities](results/published-revisions.json)
support exact lookup. The original base `30ea5f7b3434a5efe99ea51801d1ea4cf13eeb2b`
was already public and is unchanged.

The repeated bootstrap and 45-output frontend study use the compiler sources at
the local `91abd724`/`c20ed941` checkpoints. Reviewed-source validation uses
`d1376165`. The final evidence-only checkpoint `384310d0` adds their reports.

The receiver-only experiment instead starts with the `30ea5f7` compiler sources.
To reproduce its corrected preparation, use `annotate_receivers.py` from the
public equivalent of `91abd724` and `receiver_compatibility.py` from the public
equivalent of `64014f16` in that checkout. These files match the agent-local
`d17bf608` and `6349e35b` versions, respectively. Keep `CC=clang` with the
LLVM 18 toolchain for that experiment. The later GCC host cohort is labeled
separately in [the optimization report](OPTIMIZATIONS.md).

## Continuation checkpoints (2026-11-06)

The continuation starts from the unchanged public base `fa9bba371c79`. All 25
local checkpoints below retain identical public trees and ordered parent
relationships. Only commit metadata was recreated through the connected GitHub
integration; no measured file content or mode changed.

The complete integrated bootstrap source is [`5aeef325bba8`](https://github.com/den-run-ai/pystachy/commit/5aeef325bba85166a5620cd2eaf9b8c0b63368a3)
(local `9b75dd6288e0`). Use it for the clean benchmark worktree. The memory-only
candidates and experimental harness checkpoints are mapped separately below.

| Local checkpoint | Public commit with identical tree | Purpose |
|---|---|---|
| `f9dcdecf6d3c` | [`f53d1f3422d5`](https://github.com/den-run-ai/pystachy/commit/f53d1f3422d54b83f2c1cab560e3e56214da650f) | Explore compiler inlining and offline profile guidance |
| `f4826b4ec68f` | [`6da3927c6312`](https://github.com/den-run-ai/pystachy/commit/6da3927c6312af25eec8cbb01836e59a1dc871bb) | Avoid copying LLVM output for the final newline |
| `a87b5c892ebf` | [`0eec0c518a3a`](https://github.com/den-run-ai/pystachy/commit/0eec0c518a3a2384948dc38ffa7d7767622d4767) | Retain LLVM output in completed function chunks |
| `33fdda0ba8f9` | [`cdb01a5b062f`](https://github.com/den-run-ai/pystachy/commit/cdb01a5b062faa0bc6599d3aaeb3d93f2e0650ae) | Integrate compact LLVM output construction |
| `96600ad42f7d` | [`fb5d513d7643`](https://github.com/den-run-ai/pystachy/commit/fb5d513d76430705fd8eb71e3ec2d4f3962d6656) | Add opt-in LLVM inlining policies to native builds |
| `694d619f0971` | [`9f9b3d7af2a1`](https://github.com/den-run-ai/pystachy/commit/9f9b3d7af2a1561ba791e6c91248509966277e8a) | Integrate opt-in LLVM inlining controls |
| `3ee3ac97459a` | [`c05911a71ed0`](https://github.com/den-run-ai/pystachy/commit/c05911a71ed0ac7c4053c5c8751f082cff7de26c) | Prototype bounded ThinLTO importing for self builds |
| `d09dad53f339` | [`d35c93dff979`](https://github.com/den-run-ai/pystachy/commit/d35c93dff97997916941117cef1a0dbec56efb3c) | Integrate ThinLTO function-import experiment |
| `b1b1e1ccd152` | [`c8430be6efeb`](https://github.com/den-run-ai/pystachy/commit/c8430be6efebcbe8792c467f4b3f944f19280f3b) | Validate IR profile compatibility and reuse provenance |
| `2391a454174b` | [`5b5be9c80583`](https://github.com/den-run-ai/pystachy/commit/5b5be9c80583dc3341a25758cfe91ecc4b87a2d2) | Preserve known empty runtime pointer barriers in ThinLTO |
| `c07b152688e7` | [`19fa559c7fd6`](https://github.com/den-run-ai/pystachy/commit/19fa559c7fd64e9e4e58412046109abad3b82e17) | Preserve known empty asm barriers in ThinLTO experiments |
| `b3f14124f556` | [`588075f7ce26`](https://github.com/den-run-ai/pystachy/commit/588075f7ce264cc0a063cc70cf568c5daf601eea) | Compare opt-in inlining across complete bootstraps |
| `f6c76fb10759` | [`46b4bcf47f60`](https://github.com/den-run-ai/pystachy/commit/46b4bcf47f601958b11e7005c587ca9fd566d2b5) | Bound profile runtime discovery and clarify bootstrap policies |
| `f20bad228f96` | [`a6738721b39e`](https://github.com/den-run-ai/pystachy/commit/a6738721b39ea6bf1a4f826cca0108633b0f262c) | Bind ThinLTO jobs to harness provenance and test rejections |
| `6e96d64aa2c1` | [`57cf783f7574`](https://github.com/den-run-ai/pystachy/commit/57cf783f7574f45810045524b616ae8f5e5d66c4) | Bind ThinLTO experiment inputs and execution provenance |
| `b70f1578a912` | [`671a149e89b0`](https://github.com/den-run-ai/pystachy/commit/671a149e89b08894a26e9e624ece9d7527a4e419) | Validate inlining bootstrap applicability and comparison |
| `9efb3b2dcd34` | [`6345f4bda583`](https://github.com/den-run-ai/pystachy/commit/6345f4bda583426bafac5118406af17cfa0a9618) | Verify bootstrap policy applicability and temporary compiler parity |
| `33228d842308` | [`dbdb7162d5f5`](https://github.com/den-run-ai/pystachy/commit/dbdb7162d5f5c7062ac0f5a786b4f40aea121372) | Merge commit 'b3f14124' into research/compiler-partitions-next |
| `f3c0970cb7cc` | [`b4290ccc75d8`](https://github.com/den-run-ai/pystachy/commit/b4290ccc75d822aadd9fca5d6a86c193b7de14dc) | Add opt-in ThinLTO final bootstrap stage |
| `5a663cf105a7` | [`6d8831b9fd3c`](https://github.com/den-run-ai/pystachy/commit/6d8831b9fd3c03a96be2550eabce49f47d485f3e) | Bind ThinLTO publication to submitted job digest |
| `d26e29e9c8e6` | [`0f59b64f3607`](https://github.com/den-run-ai/pystachy/commit/0f59b64f3607feb8058fd8dab86222d407eae2ef) | Integrate bounded ThinLTO compiler bootstrap with bound publication |
| `767743ea6176` | [`49bb138ead61`](https://github.com/den-run-ai/pystachy/commit/49bb138ead61fe0686a754a47689b9baa6334494) | Verify default inlining parity and runtime cache reuse |
| `686287cfa99a` | [`abcb6160fdff`](https://github.com/den-run-ai/pystachy/commit/abcb6160fdff9e30d47cf9a6272ac6be8cd7b286) | Verify unchanged defaults and runtime reuse across inlining policies |
| `9b75dd6288e0` | [`5aeef325bba8`](https://github.com/den-run-ai/pystachy/commit/5aeef325bba85166a5620cd2eaf9b8c0b63368a3) | Compare imported partitions in controlled full bootstraps |
| `1c61cff0e0ab` | [`87f95de71e17`](https://github.com/den-run-ai/pystachy/commit/87f95de71e17099ff08547bb9273e1b579c92cbf) | Measure imported backend bootstrap and compiler memory tradeoffs |

[Full continuation commit, parent and tree identities](results/continuation-published-revisions.json)
provide exact lookup. The continuation report and its raw evidence retain the
original local IDs; the mappings above identify publicly retrievable equivalents.
