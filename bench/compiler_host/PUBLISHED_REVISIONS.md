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
