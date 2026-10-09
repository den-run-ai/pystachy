t = "abracadabra " * 20000
n = 0
for i in range(200):
    n += t.count("ab") + t.count("a")
print(n)
