import from_retry_state

from_retry_state.attempts[3] += 1
if from_retry_state.attempts[3] == 2:
    import from_kept_reader
    print("old bindings", from_kept_reader.use())


class Pending:
    value = 9


def pending() -> int:
    return 7


value = 13
import from_kept_reader
if from_retry_state.attempts[3] == 1:
    raise ValueError("retry")
print("kept source done")
