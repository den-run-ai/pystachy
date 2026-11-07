"""Load one verified native extension, then run the common untimed driver setup."""
import importlib.machinery
from pathlib import Path
import runpy
import sys


def main():
    directory = Path(sys.argv[1]).resolve()
    driver = sys.argv[2]
    sys.path.insert(0, str(directory))
    import bpe_tokeniser
    loaded = Path(bpe_tokeniser.__file__).resolve()
    if loaded.parent != directory or not any(
            str(loaded).endswith(suffix) for suffix in importlib.machinery.EXTENSION_SUFFIXES):
        raise RuntimeError(f"expected the freshly built native extension, got {loaded}")
    bpe_tokeniser.BPE_PATTERN = r"'s|'t|'re|'ve|'m|'ll|'d| ?[a-zA-Z]+| ?\d+| ?[^\sa-zA-Z\d]+|\s+(?!\S)|\s+"
    sys.argv = [driver, *sys.argv[3:]]
    runpy.run_path(driver, run_name="__main__")


if __name__ == "__main__":
    main()
