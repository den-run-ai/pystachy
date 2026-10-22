# tests/prepare_path.sh copies the helper into a temporary path with an unbalanced bracket.
# That module path must not change closure-containing tuples.
from closure_path_fixture import checks

print(checks(1))
