# stderr is closed when the program starts (tests/run.sh closes it for a program named
# *_closed_stderr), so CPython's sys.stderr is None: input() raises RuntimeError without reading
# stdin; uncaught, it ends the program with status 1 and no report
for prompt in ["", "prompt> "]:
    try:
        print("got", repr(input(prompt) if prompt else input()))
    except (RuntimeError, EOFError) as e:
        print(type(e).__name__, e)
input()
print("not reached")
