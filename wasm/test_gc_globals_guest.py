# Both slots stay live. The first list becomes unreachable after reassignment.
left: list[int] = [17]
right: list[int] = [23]
left = [29]
