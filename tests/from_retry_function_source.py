import from_retry_state

from_retry_state.attempts[1] += 1

def ready() -> int:
    return 1

if from_retry_state.attempts[1] == 2:
    import from_retry_function_reader

def pending() -> int:
    return 2

if from_retry_state.attempts[1] == 1:
    raise ValueError("retry")
print("function source done")
