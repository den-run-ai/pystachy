# Helper of tests/errors/inference/class_attr_class_const_module_mismatch.py.
class Branch:
    BOOL = 100


class Labels:
    NAME: str = Branch.BOOL
