import from_retry_state

from_retry_state.attempts[0] += 1

class Ready:
    value = 1

if from_retry_state.attempts[0] == 2:
    import from_retry_class_reader

class Pending:
    value = 2

if from_retry_state.attempts[0] == 1:
    raise ValueError("retry")
print("class source done")
