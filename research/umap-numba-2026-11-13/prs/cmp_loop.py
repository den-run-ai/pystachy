"""An int counter compared with floats, as a schedule does: due[i] <= step."""
import sys

rounds = int(sys.argv[1])
due = [(i % 97) * 0.5 for i in range(1000)]
taken = 0
for step in range(rounds):
    for i in range(1000):
        if due[i] <= step:
            taken += 1
print(taken)
