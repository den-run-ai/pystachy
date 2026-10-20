# error: 'warnings.WarningMessage' object has no attribute 'file'
# A recorded message keeps no file and no source, None in what CPython records, as no field holds
# an object of any type, or None
import warnings

with warnings.catch_warnings(record=True) as log:
    warnings.simplefilter("always")
    warnings.warn("x")
    print(log[0].file)
