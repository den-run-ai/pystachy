# Complete alpha.1 Lean qualification

The complete census is accepted for release commit `a73c56c92f3aad4b490307a5d1b882e487a57f55`. It executed at `6b9e89ee3eaef0c15cfe7ffb7d586ae9e4db9fd8`; both commits have the identical complete source tree `3c9a009434d68906889651d148cb29f6022d2f1f`. Required exact-main workflows pass separately in the adjacent gate/review evidence.

All 2,529 unique programs match the pinned corpus, every required check is present, and inspection/checker failures are absent. All 175 selected promoting programs have accepted storage records: 18,582/18,582 obligations are proved, with no rejected or unsupported functions. The report table lists 162 programs with nonzero storage obligations; the other 13 selected programs have zero obligations.

The full comparison against the prior census has exactly one change: the context-manager storage case improves from 7/7 to 19/19 obligations and eliminates two unsupported functions. Every other proof dictionary is identical. Existing limitations of the other bounded models remain explicitly listed in the original report; this is not a claim that every compiler obligation is proved or that the whole compiler is verified.

An independent audit reconstructed the entire Markdown report from the raw records, verified the complete inventories and live source/checker hashes, checked every recorded exit code, and confirmed the original 185 resumed records remain byte-identical. The archive includes the full old baseline, original resume prefix, final records, provenance, runner, acceptance/comparison helpers and independent receipts, with a file hash manifest.

The raw report's relative model links refer to the original source directory. Canonical model documents are under [tools/lean_boundary at the release commit](https://github.com/den-run-ai/pystachy/tree/a73c56c92f3aad4b490307a5d1b882e487a57f55/tools/lean_boundary).

This is complete source qualification evidence. Native/Docker/PyPI publication and downloaded-artifact verification are separate steps and are not claimed by this package.
