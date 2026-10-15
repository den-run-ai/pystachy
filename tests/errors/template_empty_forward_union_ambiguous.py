# error: returns an empty list taken as list[int]: give it a type first
# Forwarding cannot select between multiple matching union members.
def empty(n):
    return []


def forward(n):
    return empty(n)


result: list[str] | list[float] = forward(1)
