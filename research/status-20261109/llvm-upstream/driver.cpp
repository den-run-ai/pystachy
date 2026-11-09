#include <cstdint>
#include <cstdio>
extern "C" int64_t count(int64_t);
extern "C" void may_throw(int64_t x) { if (x >= 3) throw 0; }
int main() { std::printf("%lld %lld\n", (long long)count(0), (long long)count(7)); }  // expect: 3 7
