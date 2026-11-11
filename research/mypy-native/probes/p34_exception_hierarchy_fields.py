# CompileError(Exception) with fields and custom __init__ (mypy/errors.py)
class CompileError(Exception):
    def __init__(self, messages: list[str], use_stdout: bool = False) -> None:
        super().__init__("\n".join(messages))
        self.messages = messages
        self.use_stdout = use_stdout
try:
    raise CompileError(["a", "b"], True)
except CompileError as e:
    print(e.messages, e.use_stdout, str(e) == "a\nb")
