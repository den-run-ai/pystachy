#define pys_mpz_cmp old_cmp
#define pys_mpz_from_int old_from_int
#define pys_mpz_from_str old_from_str
#define pys_mpz_binop old_binop
#define pys_mpz_unary old_unary
#define pys_mpz_bit_length old_bit_length
#define pys_mpz_shift old_shift
#define pys_mpz_pow old_pow
#define pys_mpz_to_int old_to_int
#define pys_mpz_hash old_hash
#define pys_mpz_str old_str
#include "common.h"
#include "mpz_old.c"
