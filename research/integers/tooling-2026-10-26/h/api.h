#define DECL(p) \
  I p##cmp(void *, void *); void *p##from_int(I); void *p##from_str(Str *, I); void *p##binop(void *, void *, I); \
  void *p##unary(void *, I); I p##bit_length(void *); void *p##shift(void *, I, I); void *p##pow(void *, I); \
  I p##to_int(void *); I p##hash(void *); Str *p##str(void *);
