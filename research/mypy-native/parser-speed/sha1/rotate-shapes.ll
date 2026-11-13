define i64 @rot_and(i64 %y) {
  %x = and i64 %y, 4294967295
  %a = shl i64 %x, 5
  %b = lshr i64 %x, 27
  %o = or i64 %a, %b
  %z = and i64 %o, 4294967295
  ret i64 %z
}
define i64 @rot_trunc(i64 %y) {
  %x = and i64 %y, 4294967295
  %a = shl i64 %x, 5
  %b = lshr i64 %x, 27
  %o = or i64 %a, %b
  %t = trunc i64 %o to i32
  %z = zext i32 %t to i64
  ret i64 %z
}
define i64 @rot_i32(i64 %y) {
  %x = and i64 %y, 4294967295
  %lo = trunc i64 %x to i32
  %a = shl i32 %lo, 5
  %b = lshr i32 %lo, 27
  %o = or i32 %a, %b
  %hi = ashr i64 %x, 32
  %h32 = trunc i64 %hi to i32
  %h = shl i32 %h32, 5
  %o2 = or i32 %o, %h
  %z = zext i32 %o2 to i64
  ret i64 %z
}
define i64 @rot_i32_unknown(i64 %x) {
  %lo = trunc i64 %x to i32
  %a = shl i32 %lo, 5
  %b = lshr i32 %lo, 27
  %o = or i32 %a, %b
  %hi = ashr i64 %x, 32
  %h32 = trunc i64 %hi to i32
  %h = shl i32 %h32, 5
  %o2 = or i32 %o, %h
  %z = zext i32 %o2 to i64
  ret i64 %z
}
define i64 @sum(i64 %y, i64 %w) {
  %x = and i64 %y, 4294967295
  %lo = trunc i64 %x to i32
  %a = shl i32 %lo, 5
  %b = lshr i32 %lo, 27
  %o = or i32 %a, %b
  %z = zext i32 %o to i64
  %s = add i64 %z, %w
  %s2 = add i64 %s, 1518500249
  %r = and i64 %s2, 4294967295
  ret i64 %r
}
