/* scalar SHA-1 (FIPS 180-4), a reference point for instruction counts */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define ROL(x, n) (((x) << (n)) | ((x) >> (32 - (n))))
static void block(const unsigned char *m, uint32_t *h) {
  uint32_t w[80], a = h[0], b = h[1], c = h[2], d = h[3], e = h[4], t;
  for (int i = 0; i < 16; i++)
    w[i] = (uint32_t)m[4 * i] << 24 | (uint32_t)m[4 * i + 1] << 16 | (uint32_t)m[4 * i + 2] << 8 | m[4 * i + 3];
  for (int i = 16; i < 80; i++) w[i] = ROL(w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16], 1);
  for (int i = 0; i < 80; i++) {
    uint32_t f, k;
    if (i < 20) { f = (b & c) | (~b & d); k = 0x5A827999; }
    else if (i < 40) { f = b ^ c ^ d; k = 0x6ED9EBA1; }
    else if (i < 60) { f = (b & c) | (b & d) | (c & d); k = 0x8F1BBCDC; }
    else { f = b ^ c ^ d; k = 0xCA62C1D6; }
    t = ROL(a, 5) + f + e + k + w[i];
    e = d; d = c; c = ROL(b, 30); b = a; a = t;
  }
  h[0] += a; h[1] += b; h[2] += c; h[3] += d; h[4] += e;
}
int main(int argc, char **argv) {
  FILE *f = fopen(argv[1], "rb");
  static unsigned char buf[1 << 21];
  size_t n = fread(buf, 1, sizeof buf - 128, f);
  int rounds = atoi(argv[2]);
  uint32_t h[5];
  for (int r = 0; r < rounds; r++) {
    h[0] = 0x67452301; h[1] = 0xEFCDAB89; h[2] = 0x98BADCFE; h[3] = 0x10325476; h[4] = 0xC3D2E1F0;
    size_t full = n - n % 64, off;
    for (off = 0; off < full; off += 64) block(buf + off, h);
    unsigned char tail[128];
    size_t rest = n - full, tl = rest + 9 <= 64 ? 64 : 128;
    memset(tail, 0, sizeof tail);
    memcpy(tail, buf + full, rest);
    tail[rest] = 0x80;
    uint64_t bits = (uint64_t)n * 8;
    for (int i = 0; i < 8; i++) tail[tl - 1 - i] = (unsigned char)(bits >> (8 * i));
    for (off = 0; off < tl; off += 64) block(tail + off, h);
  }
  printf("%zu %08x%08x%08x%08x%08x\n", n, h[0], h[1], h[2], h[3], h[4]);
  return 0;
}
