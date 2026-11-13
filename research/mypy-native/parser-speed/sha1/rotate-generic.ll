define i64 @known(i64 %y, i64 %w) {
  %x = and i64 %y, 4294967295
  %lo = trunc i64 %x to i32
  %a = shl i32 %lo, 5
  %s = ashr i64 %x, 27
  %b = trunc i64 %s to i32
  %o = or i32 %a, %b
  %wl = trunc i64 %w to i32
  %sum = add i32 %o, %wl
  %sum2 = add i32 %sum, 1518500249
  %z = zext i32 %sum2 to i64
  ret i64 %z
}
define i64 @unknown(i64 %x, i64 %w) {
  %lo = trunc i64 %x to i32
  %a = shl i32 %lo, 5
  %s = ashr i64 %x, 27
  %b = trunc i64 %s to i32
  %o = or i32 %a, %b
  %wl = trunc i64 %w to i32
  %sum = add i32 %o, %wl
  %z = zext i32 %sum to i64
  ret i64 %z
}
define i64 @old_unknown(i64 %x, i64 %w) {
  %a = shl i64 %x, 5
  %s = ashr i64 %x, 27
  %o = or i64 %a, %s
  %m = and i64 %o, 4294967295
  %sum = add i64 %m, %w
  %z = and i64 %sum, 4294967295
  ret i64 %z
}
