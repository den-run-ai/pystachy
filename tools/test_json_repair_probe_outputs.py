"""Reject plausible checksum-preserving corruption in measured repair probes."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def run_probe(name, args, repair):
    module = ModuleType("json_repair")
    module.repair_json = repair
    script = ROOT / "bench/json_repair" / name
    with patch.dict(sys.modules, {"json_repair": module}), \
            patch.object(sys, "argv", [str(script), *args]), \
            contextlib.redirect_stdout(io.StringIO()):
        return runpy.run_path(str(script), run_name="__main__")


class CompleteRepairProbeTests(unittest.TestCase):
    def test_mixed_rejects_same_weight_changed_nested_content(self):
        calls = 0

        def repair(source, **options):
            nonlocal calls
            calls += 1
            # The mixed probe's weight reads neither this field nor its item.
            return {"ok": True, "payload": {"value": 1 if calls <= 10 else 2}}

        with self.assertRaisesRegex(ValueError, "complete repaired result"):
            run_probe("bench.py", ["1", "1", "0"], repair)

    def test_mixed_rejects_changed_key_order_with_same_weight(self):
        calls = 0

        def repair(source, **options):
            nonlocal calls
            calls += 1
            return {"ok": True, "other": 1} if calls <= 10 else {"other": 1, "ok": True}

        with self.assertRaisesRegex(ValueError, "dictionary order"):
            run_probe("bench.py", ["1", "1", "0"], repair)

    def test_logged_repair_rejects_same_count_changed_message(self):
        calls = 0

        def repair(source, **options):
            nonlocal calls
            calls += 1
            return {"a": "x,x,"}, [{"text": "before" if calls == 1 else "after!", "context": "{a:"}]

        with self.assertRaisesRegex(ValueError, "log text changed"):
            run_probe("scaling.py", ["logs", "2", "1", "1", "0"], repair)

    def test_logged_repair_rejects_same_count_changed_context(self):
        calls = 0

        def repair(source, **options):
            nonlocal calls
            calls += 1
            return {"a": "x,x,"}, [{"text": "repaired", "context": "{a:" if calls == 1 else "{b:"}]

        with self.assertRaisesRegex(ValueError, "log text changed"):
            run_probe("scaling.py", ["logs", "2", "1", "1", "0"], repair)

    def test_warmup_corruption_fails_before_timed_batches(self):
        calls = 0

        def repair(source, **options):
            nonlocal calls
            calls += 1
            return {"a": "x,x,"}, [{"text": "repaired", "context": "{a:" if calls == 1 else "{b:"}]

        with self.assertRaisesRegex(ValueError, "log text changed"):
            run_probe("scaling.py", ["logs", "2", "1", "1", "1"], repair)
        self.assertEqual(calls, 2, "a corrupt warmup must prevent measured work")


if __name__ == "__main__":
    unittest.main()
