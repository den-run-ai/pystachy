import from_retry_state

from_retry_state.attempts[2] += 1

ready = 1

if from_retry_state.attempts[2] == 2:
    import from_retry_global_reader

pending = 2

if from_retry_state.attempts[2] == 1:
    raise ValueError("retry")
print("global source done")
