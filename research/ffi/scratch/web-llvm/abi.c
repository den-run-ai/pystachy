typedef struct { double x, y; } P2;
typedef struct { long a, b, c; } L3;
typedef struct { int a; float b; } IF;
P2 f2(P2 p) { return p; }
L3 f3(L3 p) { return p; }
IF f4(IF p, _Bool b, char c, short s) { return p; }
