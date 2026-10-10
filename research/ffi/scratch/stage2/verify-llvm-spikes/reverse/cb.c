long jit_side(long);               /* defined in JIT'd IR */
long c_calls_back(long x) { return jit_side(x) + 1; }
long c_calls_ptr(long (*f)(long), long x) { return f(x) + 1; }
