# An uncaught TOMLDecodeError's line names its class as the tomllib package gives it, which
# assigns its __module__: tomllib.TOMLDecodeError, not tomllib._parser's
import tomllib

print(tomllib.loads("a = 1"), tomllib.TOMLDecodeError.__module__)
tomllib.loads("a = 1\nb = [1,\n")
