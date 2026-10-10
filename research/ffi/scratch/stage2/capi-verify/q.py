import tomllib, sys
d = tomllib.load(open(sys.argv[1],'rb'))
names = sys.argv[2:]
idx = {}
for kind, ents in d.items():
    for n, e in ents.items():
        idx.setdefault(n, []).append((kind, e))
for n in names:
    if n in idx:
        for kind, e in idx[n]:
            print(f"{n:40s} {kind:8s} " + " ".join(f"{k}={v}" for k,v in e.items()))
    else:
        print(f"{n:40s} NOT FOUND")
