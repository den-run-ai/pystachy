# error: type_statement_twice.py:2: error: 'type' statements are only supported at a module's top level, for a name that no other statement binds
type Row = list[str]
type Row = list[int]
print("never")
