#define pys_mpz_cmp new_cmp
#define pys_mpz_from_int new_from_int
#define pys_mpz_from_str new_from_str
#define pys_mpz_binop new_binop
#define pys_mpz_unary new_unary
#define pys_mpz_bit_length new_bit_length
#define pys_mpz_shift new_shift
#define pys_mpz_pow new_pow
#define pys_mpz_to_int new_to_int
#define pys_mpz_hash new_hash
#define pys_mpz_str new_str
#include "common.h"
#include "mpz_arith.c"
