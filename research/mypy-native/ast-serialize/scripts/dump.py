"""Generic structural dump of mypy's binary AST format (tags, values, offsets)."""
import sys

def read_int(b, p):
    first = b[p]; p += 1
    if first == 15:
        sz = None
        v, p = read_int(b, p)
        n = v >> 1; neg = v & 1
        val = int.from_bytes(b[p:p+n], 'little'); p += n
        return (-val if neg else val), p
    if first & 1 == 0:
        return (first >> 1) - 10, p
    if first & 2 == 0:
        second = b[p]; p += 1
        return (second << 6) + (first >> 2) - 100, p
    second = b[p]; third = b[p+1] | (b[p+2] << 8); p += 3
    return (third << 13) + (second << 5) + (first >> 3) - 10000, p

NAMES = {
 0:'False',1:'True',2:'None',3:'INT',4:'STR',5:'BYTES',6:'FLOAT',20:'LIST',21:'LIST_INT',30:'DICT',53:'Decorator',60:'ClassDef',152:'LOC',255:'END',
 160:'ExprStmt',161:'Call',162:'Name',163:'Str',164:'Import',165:'Member',166:'Op',167:'Int',168:'If',169:'Assign',170:'Tuple',171:'Block',172:'Index',
 173:'List',174:'Set',175:'Return',176:'While',177:'Comparison',178:'BoolOp',179:'FuncDef',180:'Pass',181:'Float',182:'Unary',183:'Dict',184:'Complex',
 185:'Slice',186:'Temp',187:'Raise',188:'Break',189:'Continue',190:'Gen',191:'Yield',192:'YieldFrom',193:'ListComp',194:'SetComp',195:'DictComp',
 196:'ImportFrom',197:'Assert',198:'For',199:'With',200:'OpAssign',201:'Try',202:'Ellipsis',203:'Cond',204:'Del',205:'FString',206:'FStrInterp',
 207:'Lambda',208:'Walrus',209:'Star',210:'Bytes',211:'Global',212:'Nonlocal',213:'Await',214:'BigInt',215:'ImportAll',216:'Match',217:'AsPat',
 218:'OrPat',219:'ValuePat',220:'SingletonPat',221:'SeqPat',222:'StarPat',223:'MappingPat',224:'ClassPat',225:'TypeAlias',226:'ImportMeta',
 227:'ImportFromMeta',228:'ImportAllMeta',229:'TString',104:'UnboundType',112:'TupleType',113:'TypedDictType',115:'UnionType',118:'TypeList',
 119:'EllipsisType',120:'RawExprType',121:'CallType',105:'UnpackType'}

def tokens(b):
    """Yield (offset, text) items for a byte stream, best effort."""
    p = 0
    out = []
    while p < len(b):
        start = p
        t = b[p]; p += 1
        name = NAMES.get(t, f'tag{t}')
        try:
            if t == 3:
                v, p = read_int(b, p); out.append((start, f'{v}'))
            elif t == 4 or t == 5:
                n, p = read_int(b, p); s = b[p:p+n]; p += n; out.append((start, repr(s.decode('utf-8', 'replace')) if t == 4 else repr(s)))
            elif t == 20:
                n, p = read_int(b, p); out.append((start, f'[{n}]'))
            elif t == 21:
                n, p = read_int(b, p); vals = []
                for _ in range(n):
                    v, p = read_int(b, p); vals.append(v)
                out.append((start, f'ints{vals}'))
            elif t == 152:
                vals = []
                for _ in range(4):
                    v, p = read_int(b, p); vals.append(v)
                out.append((start, f'@{vals[0]}:{vals[1]}+{vals[2]}:{vals[3]}'))
            elif t == 6:
                import struct
                out.append((start, repr(struct.unpack('<d', b[p:p+8])[0]))); p += 8
            elif t == 30:
                n, p = read_int(b, p); out.append((start, f'dict[{n}]'))
            else:
                out.append((start, name))
        except IndexError:
            out.append((start, f'<truncated {name}>'))
            break
    return out

def show(b):
    return ' '.join(x for _, x in tokens(b))

if __name__ == '__main__':
    import ast_serialize
    src = sys.argv[1].encode().decode('unicode_escape') if len(sys.argv) > 1 else 'x = 1\n'
    r = ast_serialize.parse('t.py', src)
    print(show(r[0]))
    print(r[1:3])
    print(show(r[3]))
    print(r[4])
