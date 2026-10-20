# error: cannot iterate over tuple[str,None]: its items have different types
# warn() checks each of skip_file_prefixes, which a tuple of items of different types cannot give
# one by one; CPython raises TypeError for its None ("Found non-str 'NoneType' in
# skip_file_prefixes.") where the call runs
import warnings

warnings.warn("mixed", skip_file_prefixes=("/nowhere", None))
