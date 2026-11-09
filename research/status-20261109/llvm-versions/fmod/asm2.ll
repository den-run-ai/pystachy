declare ptr @alloc()
declare void @collect()
declare void @use(i64)
define void @f(i64 %n) {
entry:
  %p = call ptr @alloc()
  %v = load i64, ptr %p
  call void @collect()
  call void asm sideeffect "", "r"(ptr %p)
  call void @use(i64 %v)
  ret void
}
