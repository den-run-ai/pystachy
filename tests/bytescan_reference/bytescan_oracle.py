"""Load only the shipped scalar helper, without putting lib/ ahead of stdlib."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "lib" / "_pystachy_bytescan.py"
spec = importlib.util.spec_from_file_location("_bytescan_scalar_oracle", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
scan = module.scan
