"""Structural drift controls for the declared Frame contract; no compiler mutation."""
import unittest

from compiler_state_contract import read_sources, validate_sources


class FrameContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = read_sources()

    def changed(self, index, old, new):
        sources = list(self.sources)
        self.assertIn(old, sources[index])
        sources[index] = sources[index].replace(old, new, 1)
        return validate_sources(*sources)

    def test_current_tree(self):
        self.assertEqual(validate_sources(*self.sources), [])

    def test_missing_frame_field(self):
        errors = self.changed(1, "        self.lcsoft: list[bool] = []\n", "")
        self.assertIn("gen_save has unexpected field lcsoft", errors)
        self.assertIn("gen_restore has unexpected field lcsoft", errors)

    def test_wrong_saved_source(self):
        errors = self.changed(2, "fr.line = self.line", "fr.line = self.n")
        self.assertIn("gen_save must transfer fr.line from self.line", errors)

    def test_missing_restore(self):
        errors = self.changed(2, "    self.line = fr.line\n", "")
        self.assertIn("gen_restore is missing line", errors)

    def test_wrong_restored_source(self):
        errors = self.changed(2, "self.line = fr.line", "self.line = fr.n")
        self.assertIn("gen_restore must transfer self.line from fr.line", errors)

    def test_wrong_constructor_argument(self):
        errors = self.changed(2, "Frame(self.curfn, self.fn, self.blk)", "Frame(self.curfn, self.blk, self.fn)")
        self.assertIn("gen_save must construct Frame(self.curfn, self.fn, self.blk)", errors)

    def test_wrong_constructor_assignment(self):
        # Limit mutation to Frame, not other records that also assign self.fn.
        sources = list(self.sources)
        before, frame = sources[1].split("class Frame:", 1)
        sources[1] = before + "class Frame:" + frame.replace("self.fn = fn", "self.fn = blk", 1)
        self.assertIn("Frame constructor must initialize fn from fn", validate_sources(*sources))

    def test_new_frame_field_without_gen_initialization(self):
        sources = list(self.sources)
        before, frame = sources[1].split("class Frame:", 1)
        sources[1] = before + "class Frame:" + frame.replace("self.fn = fn", "self.extra_state = 0\n        self.fn = fn", 1)
        errors = validate_sources(*sources)
        self.assertIn("Frame field extra_state is absent from Gen.__init__", errors)
        self.assertIn("gen_save is missing extra_state", errors)
        self.assertIn("gen_restore is missing extra_state", errors)

    def test_duplicate_transfer(self):
        for old, expected in (("fr.line = self.line", "gen_save transfers line 2 times"),
                              ("self.line = fr.line", "gen_restore transfers line 2 times")):
            with self.subTest(old=old):
                self.assertIn(expected, self.changed(2, old, old + "\n    " + old))

    def test_conditional_transfer_is_not_unconditional_save(self):
        errors = self.changed(2, "    fr.line = self.line", "    if self.term:\n        fr.line = self.line")
        self.assertIn("gen_save transfers must be direct single assignments", errors)

    def test_duplicate_frame_field(self):
        errors = self.changed(1, "        self.lcsoft: list[bool] = []", "        self.lcsoft: list[bool] = []\n        self.lcsoft = []")
        self.assertIn("Frame initializes lcsoft 2 times", errors)

    def test_conditional_frame_initialization(self):
        sources = list(self.sources)
        before, frame = sources[1].split("class Frame:", 1)
        sources[1] = before + "class Frame:" + frame.replace(
            "        self.line = 0", "        if False:\n            self.line = 0", 1)
        self.assertIn("Frame initialization must use unconditional direct assignments",
                      validate_sources(*sources))

    def test_new_gen_only_field_is_outside_contract(self):
        sources = list(self.sources)
        before, gen = sources[0].split("class Gen:", 1)
        sources[0] = before + "class Gen:" + gen.replace("def __init__(self):", "def __init__(self):\n        self.unclassified_state = 0", 1)
        self.assertEqual(validate_sources(*sources), [])


if __name__ == "__main__":
    unittest.main()
