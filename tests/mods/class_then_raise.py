# A module whose code defines a class, then raises: an import of it never binds its name
# (tests/programs/reflection/isinstance_failed_import.py)
class Made:
    pass


raise ValueError("raised after the class")
