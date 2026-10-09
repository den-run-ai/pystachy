t = "abcdefghij" * 20000 + "needle"
n = 0
for i in range(300):
    n += t.find("needle", i % 7) + t.find("zz", i)
print(n)
