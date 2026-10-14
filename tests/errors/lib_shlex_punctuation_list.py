# error: expected str, got list[str]
# lib/shlex's punctuation_chars is a bool or a str (lib/README.md): CPython also takes a list of
# characters
import shlex

print(list(shlex.shlex("a|b", punctuation_chars=["|"])))
