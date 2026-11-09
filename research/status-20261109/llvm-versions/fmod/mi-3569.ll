define internal fastcc void @main.init() unnamed_addr {
entry:
  %t2 = call double @pys_float_str(ptr nonnull @s.0)
  store double %t2, ptr @g.NAN, align 8
  %0 = load ptr, ptr @args, align 8, !tbaa !5
  %t8 = load i64, ptr %0, align 4
  %t9 = icmp sgt i64 %t8, 1
  br i1 %t9, label %pys_list_get.exit, label %L12

pys_list_get.exit:                                ; preds = %entry
  %1 = getelementptr inbounds nuw i8, ptr %0, i64 16
  %2 = load ptr, ptr %1, align 8, !tbaa !9
  %3 = getelementptr inbounds nuw i8, ptr %2, i64 8
  %4 = load i64, ptr %3, align 8, !tbaa !13
  %t18 = inttoptr i64 %4 to ptr
  %t19 = call double @pys_float_str(ptr %t18)
  br label %L12

L12:                                              ; preds = %entry, %pys_list_get.exit
  %t21 = phi double [ %t19, %pys_list_get.exit ], [ %t2, %entry ]
  store double %t21, ptr @g.x, align 8
  %t29 = load double, ptr @g.NAN, align 8
  %5 = call double @llvm.fabs.f64(double %t29) #39
  %6 = fcmp une double %5, 0x7FF0000000000000
  br i1 %6, label %pys_m_fmod.exit, label %7

7:                                                ; preds = %L12
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit:                                  ; preds = %L12
  %t39 = load double, ptr @g.x, align 8
  %8 = call double @llvm.fabs.f64(double %t39) #39
  %9 = fcmp une double %8, 0x7FF0000000000000
  br i1 %9, label %pys_m_fmod.exit2, label %10

10:                                               ; preds = %pys_m_fmod.exit
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit2:                                 ; preds = %pys_m_fmod.exit
  %t46 = load double, ptr @g.NAN, align 8
  %11 = call double @llvm.fabs.f64(double %t46) #39
  %12 = fcmp une double %11, 0x7FF0000000000000
  br i1 %12, label %pys_m_fmod.exit3, label %13

13:                                               ; preds = %pys_m_fmod.exit2
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit3:                                 ; preds = %pys_m_fmod.exit2
  %t51 = load double, ptr @g.NAN, align 8
  %14 = call double @llvm.fabs.f64(double %t51) #39
  %15 = fcmp une double %14, 0x7FF0000000000000
  br i1 %15, label %pys_m_fmod.exit4, label %16

16:                                               ; preds = %pys_m_fmod.exit3
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit4:                                 ; preds = %pys_m_fmod.exit3
  %17 = frem nnan double %t46, 1.000000e+00
  %18 = frem nnan double %t51, 1.000000e+00
  %t53 = fcmp une double %17, %18
  call void @pys_write(ptr nonnull @s.4, i64 1)
  call void @pys_write(ptr nonnull @s.1, i64 1)
  call void @pys_write(ptr nonnull @s.4, i64 1)
  call void @pys_write(ptr nonnull @s.1, i64 1)
  %t56 = select i1 %t53, ptr @s.3, ptr @s.4
  call void @pys_write(ptr nonnull %t56, i64 1)
  call void @pys_write(ptr nonnull @s.2, i64 1)
  ret void
}
