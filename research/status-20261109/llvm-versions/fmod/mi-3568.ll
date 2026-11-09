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
  %3 = getelementptr inbounds nuw %struct.Slot, ptr %2, i64 1
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
  %7 = fcmp uno double 1.000000e+00, %t29
  %8 = or i1 %7, %6
  br i1 %8, label %pys_m_fmod.exit, label %9

9:                                                ; preds = %L12
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit:                                  ; preds = %L12
  %10 = call double @fmod(double noundef %t29, double noundef 1.000000e+00) #25, !tbaa !15
  %t39 = load double, ptr @g.x, align 8
  %11 = call double @llvm.fabs.f64(double %t39) #39
  %12 = fcmp une double %11, 0x7FF0000000000000
  %13 = fcmp uno double 1.000000e+00, %t39
  %14 = or i1 %13, %12
  br i1 %14, label %pys_m_fmod.exit2, label %15

15:                                               ; preds = %pys_m_fmod.exit
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit2:                                 ; preds = %pys_m_fmod.exit
  %16 = call double @fmod(double noundef %t39, double noundef 1.000000e+00) #25, !tbaa !15
  %t46 = load double, ptr @g.NAN, align 8
  %17 = call double @llvm.fabs.f64(double %t46) #39
  %18 = fcmp une double %17, 0x7FF0000000000000
  %19 = fcmp uno double 1.000000e+00, %t46
  %20 = or i1 %19, %18
  br i1 %20, label %pys_m_fmod.exit3, label %21

21:                                               ; preds = %pys_m_fmod.exit2
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit3:                                 ; preds = %pys_m_fmod.exit2
  %22 = call double @fmod(double noundef %t46, double noundef 1.000000e+00) #25, !tbaa !15
  %23 = fcmp uno double %16, 0.000000e+00
  %24 = zext i1 %23 to i64
  %t42.not = icmp eq i64 %24, 0
  %25 = fcmp uno double %10, 0.000000e+00
  %26 = zext i1 %25 to i64
  %t32.not = icmp eq i64 %26, 0
  %t51 = load double, ptr @g.NAN, align 8
  %27 = call double @llvm.fabs.f64(double %t51) #39
  %28 = fcmp une double %27, 0x7FF0000000000000
  %29 = fcmp uno double 1.000000e+00, %t51
  %30 = or i1 %29, %28
  br i1 %30, label %pys_m_fmod.exit4, label %31

31:                                               ; preds = %pys_m_fmod.exit3
  call void @pys_fail(ptr noundef nonnull @.str.62) #40
  unreachable

pys_m_fmod.exit4:                                 ; preds = %pys_m_fmod.exit3
  %32 = call double @fmod(double noundef %t51, double noundef 1.000000e+00) #25, !tbaa !15
  %t53 = fcmp une double %22, %32
  %t54 = select i1 %t32.not, ptr @s.4, ptr @s.3
  call void @pys_write(ptr nonnull %t54, i64 1)
  call void @pys_write(ptr nonnull @s.1, i64 1)
  %t55 = select i1 %t42.not, ptr @s.4, ptr @s.3
  call void @pys_write(ptr nonnull %t55, i64 1)
  call void @pys_write(ptr nonnull @s.1, i64 1)
  %t56 = select i1 %t53, ptr @s.3, ptr @s.4
  call void @pys_write(ptr nonnull %t56, i64 1)
  call void @pys_write(ptr nonnull @s.2, i64 1)
  ret void
}
