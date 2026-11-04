"""Guard the distinction between wheel inventory, import IR and API execution."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

import pypi_inventory as census


class InventoryTests(unittest.TestCase):
    def test_wheel_scan_checks_hash_and_records_incomplete_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = io.BytesIO()
            with zipfile.ZipFile(data, "w") as wheel:
                wheel.writestr("demo-1.data/purelib/demo/__init__.py",
                               "from pathlib import Path\ntry:\n import logging\nexcept ImportError:\n pass\n"
                               "if TYPE_CHECKING:\n import enum\ndef run():\n import argparse\n")
                wheel.writestr("tests/test_demo.py", "import threading")
                wheel.writestr("demo/bad.py", "if :")
            payload = data.getvalue()
            filename = "demo-1-py3-none-any.whl"
            (root / filename).write_bytes(payload)
            row = {"rank": 1, "project": "demo", "version": "1", "status": "pure-wheel", "filename": filename,
                   "size": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            result = census.scan(row, root)
            self.assertEqual(result["status"], "partial")
            self.assertEqual((result["stdlib"], result["parsed"], result["skipped"]), (["pathlib", "pathlib.Path"], 1, 1))
            self.assertEqual(census.scan(row | {"sha256": "wrong"}, root)["status"], "integrity-error")

    def test_resolved_submodules_are_distinct_from_attributes(self):
        names = ["json.loads", "importlib.resources", "importlib.resources.files"]
        known = {"json", "importlib", "importlib.resources"}
        self.assertEqual(census.profile_modules(names, known), {"json", "importlib.resources"})

    def test_unscanned_inputs_cannot_count_as_all_imports_available(self):
        rows = [
            {"rank": 1, "project": "stubs", "status": "no-source", "stdlib": [], "parsed": 0},
            {"rank": 2, "project": "simple", "status": "scanned", "stdlib": [], "parsed": 1},
            {"rank": 3, "project": "missing", "status": "missing"},
        ]
        with mock.patch.object(census, "module_ir", return_value={"modules": {}}):
            result = census.compare(rows, "old", "new", 1, 1)["projects"]
        self.assertNotIn("after", result[0])
        self.assertEqual(result[1]["after"], [])
        self.assertNotIn("after", result[2])

    def test_yanked_pure_wheel_does_not_hide_binary_only_release(self):
        release = [{"yanked": True, "filename": "demo-1-py3-none-any.whl", "packagetype": "bdist_wheel"},
                   {"yanked": False, "filename": "demo-1-cp313-cp313-linux_x86_64.whl", "packagetype": "bdist_wheel"}]
        self.assertEqual(census.pure_release(release), {"status": "binary-only"})
