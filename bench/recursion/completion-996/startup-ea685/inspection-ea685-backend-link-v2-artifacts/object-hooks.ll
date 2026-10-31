declare void @pys_obj_hooks(ptr, ptr, ptr)
define internal void @pys.obj.hooks() {
  call void @pys_obj_hooks(ptr @pys_obj_eq, ptr @pys_obj_cmp, ptr @pys_obj_repr)
  ret void
}
@llvm.global_ctors = appending global [1 x { i32, ptr, ptr }] [{ i32, ptr, ptr } { i32 0, ptr @pys.obj.hooks, ptr null }]
