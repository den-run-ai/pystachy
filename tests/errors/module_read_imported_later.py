# error: the type of 'KEY' of module emods.later_keys is not known here, as this module's code is compiled before that module's code, which it imports later: import emods.later_keys at the top of tests/errors/emods/early_reader.py
import emods.early_reader
import emods.later_keys

print(emods.later_keys.KEY)
