	.file	"matmul.c"
	.text
	.section .rdata,"dr"
	.align 32
A:
	.long	1
	.long	2
	.long	3
	.long	4
	.long	5
	.long	6
	.long	7
	.long	8
	.long	9
	.align 32
B:
	.long	9
	.long	8
	.long	7
	.long	6
	.long	5
	.long	4
	.long	3
	.long	2
	.long	1
	.align 32
REF:
	.long	30
	.long	24
	.long	18
	.long	84
	.long	69
	.long	54
	.long	138
	.long	114
	.long	90
	.align 8
.LC0:
	.ascii "=== C \350\257\255\350\250\200\344\270\211\351\207\215\345\276\252\347\216\257\345\256\236\347\216\260 3x3 \347\237\251\351\230\265\344\271\230\346\263\225 (N=%d) ===\12\0"
.LC1:
	.ascii "A =\0"
.LC2:
	.ascii "  [\0"
.LC3:
	.ascii " %4d\0"
.LC4:
	.ascii " ]\0"
.LC5:
	.ascii "B =\0"
.LC6:
	.ascii "C = A x B =\0"
.LC7:
	.ascii "C_FLAT =\0"
.LC8:
	.ascii " %d\0"
.LC9:
	.ascii "CHECKSUM = %ld\12\0"
	.align 8
.LC10:
	.ascii "--- \344\270\216\346\240\207\345\207\206\347\255\224\346\241\210\351\200\220\351\241\271\346\257\224\345\257\271 ---\0"
	.align 8
.LC11:
	.ascii "  C[%d][%d] = %4d  REF = %4d  PASS\12\0"
	.align 8
.LC12:
	.ascii "  C[%d][%d] = %4d  REF = %4d  FAIL\12\0"
.LC13:
	.ascii "RESULT: %d/%d PASS\0"
.LC14:
	.ascii "  ==> ALL PASS\0"
.LC15:
	.ascii "  ==> MISMATCH\0"
	.text
	.globl	main
	.def	main;	.scl	2;	.type	32;	.endef
	.seh_proc	main
main:
	pushq	%rbp
	.seh_pushreg	%rbp
	movq	%rsp, %rbp
	.seh_setframe	%rbp, 0
	subq	$112, %rsp
	.seh_stackalloc	112
	.seh_endprologue
	call	__main
	movl	$0, -16(%rbp)
	movl	$0, -20(%rbp)
	movl	$0, -24(%rbp)
	movl	$0, -4(%rbp)
	jmp	.L2
.L7:
	movl	$0, -8(%rbp)
	jmp	.L3
.L6:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	$0, -64(%rbp,%rax,4)
	movl	$0, -12(%rbp)
	jmp	.L4
.L5:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %r8d
	movl	-12(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	leaq	0(,%rax,4), %rdx
	leaq	A(%rip), %rax
	movl	(%rdx,%rax), %ecx
	movl	-8(%rbp), %eax
	movslq	%eax, %r9
	movl	-12(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%r9, %rax
	leaq	0(,%rax,4), %rdx
	leaq	B(%rip), %rax
	movl	(%rdx,%rax), %eax
	imull	%ecx, %eax
	leal	(%r8,%rax), %ecx
	movl	-8(%rbp), %eax
	movslq	%eax, %r8
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%r8, %rax
	movl	%ecx, -64(%rbp,%rax,4)
	addl	$1, -12(%rbp)
.L4:
	cmpl	$2, -12(%rbp)
	jle	.L5
	addl	$1, -8(%rbp)
.L3:
	cmpl	$2, -8(%rbp)
	jle	.L6
	addl	$1, -4(%rbp)
.L2:
	cmpl	$2, -4(%rbp)
	jle	.L7
	leaq	.LC0(%rip), %rax
	movl	$3, %edx
	movq	%rax, %rcx
	call	__mingw_printf
	leaq	.LC1(%rip), %rax
	movq	%rax, %rcx
	call	puts
	movl	$0, -4(%rbp)
	jmp	.L8
.L11:
	leaq	.LC2(%rip), %rax
	movq	%rax, %rcx
	call	__mingw_printf
	movl	$0, -8(%rbp)
	jmp	.L9
.L10:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	leaq	0(,%rax,4), %rdx
	leaq	A(%rip), %rax
	movl	(%rdx,%rax), %eax
	leaq	.LC3(%rip), %rcx
	movl	%eax, %edx
	call	__mingw_printf
	addl	$1, -8(%rbp)
.L9:
	cmpl	$2, -8(%rbp)
	jle	.L10
	leaq	.LC4(%rip), %rax
	movq	%rax, %rcx
	call	puts
	addl	$1, -4(%rbp)
.L8:
	cmpl	$2, -4(%rbp)
	jle	.L11
	leaq	.LC5(%rip), %rax
	movq	%rax, %rcx
	call	puts
	movl	$0, -4(%rbp)
	jmp	.L12
.L15:
	leaq	.LC2(%rip), %rax
	movq	%rax, %rcx
	call	__mingw_printf
	movl	$0, -8(%rbp)
	jmp	.L13
.L14:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	leaq	0(,%rax,4), %rdx
	leaq	B(%rip), %rax
	movl	(%rdx,%rax), %eax
	leaq	.LC3(%rip), %rcx
	movl	%eax, %edx
	call	__mingw_printf
	addl	$1, -8(%rbp)
.L13:
	cmpl	$2, -8(%rbp)
	jle	.L14
	leaq	.LC4(%rip), %rax
	movq	%rax, %rcx
	call	puts
	addl	$1, -4(%rbp)
.L12:
	cmpl	$2, -4(%rbp)
	jle	.L15
	leaq	.LC6(%rip), %rax
	movq	%rax, %rcx
	call	puts
	movl	$0, -4(%rbp)
	jmp	.L16
.L19:
	leaq	.LC2(%rip), %rax
	movq	%rax, %rcx
	call	__mingw_printf
	movl	$0, -8(%rbp)
	jmp	.L17
.L18:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %eax
	leaq	.LC3(%rip), %rcx
	movl	%eax, %edx
	call	__mingw_printf
	addl	$1, -8(%rbp)
.L17:
	cmpl	$2, -8(%rbp)
	jle	.L18
	leaq	.LC4(%rip), %rax
	movq	%rax, %rcx
	call	puts
	addl	$1, -4(%rbp)
.L16:
	cmpl	$2, -4(%rbp)
	jle	.L19
	leaq	.LC7(%rip), %rax
	movq	%rax, %rcx
	call	__mingw_printf
	movl	$0, -4(%rbp)
	jmp	.L20
.L23:
	movl	$0, -8(%rbp)
	jmp	.L21
.L22:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %eax
	leaq	.LC8(%rip), %rcx
	movl	%eax, %edx
	call	__mingw_printf
	addl	$1, -8(%rbp)
.L21:
	cmpl	$2, -8(%rbp)
	jle	.L22
	addl	$1, -4(%rbp)
.L20:
	cmpl	$2, -4(%rbp)
	jle	.L23
	movl	$10, %ecx
	call	putchar
	movl	$0, -4(%rbp)
	jmp	.L24
.L27:
	movl	$0, -8(%rbp)
	jmp	.L25
.L26:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %eax
	addl	%eax, -16(%rbp)
	addl	$1, -8(%rbp)
.L25:
	cmpl	$2, -8(%rbp)
	jle	.L26
	addl	$1, -4(%rbp)
.L24:
	cmpl	$2, -4(%rbp)
	jle	.L27
	movl	-16(%rbp), %eax
	leaq	.LC9(%rip), %rcx
	movl	%eax, %edx
	call	__mingw_printf
	leaq	.LC10(%rip), %rax
	movq	%rax, %rcx
	call	puts
	movl	$0, -4(%rbp)
	jmp	.L28
.L33:
	movl	$0, -8(%rbp)
	jmp	.L29
.L32:
	addl	$1, -24(%rbp)
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %ecx
	movl	-8(%rbp), %eax
	movslq	%eax, %r8
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%r8, %rax
	leaq	0(,%rax,4), %rdx
	leaq	REF(%rip), %rax
	movl	(%rdx,%rax), %eax
	cmpl	%eax, %ecx
	jne	.L30
	addl	$1, -20(%rbp)
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	leaq	0(,%rax,4), %rdx
	leaq	REF(%rip), %rax
	movl	(%rdx,%rax), %r8d
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %r9d
	movl	-8(%rbp), %edx
	movl	-4(%rbp), %eax
	leaq	.LC11(%rip), %rcx
	movl	%r8d, 32(%rsp)
	movl	%edx, %r8d
	movl	%eax, %edx
	call	__mingw_printf
	jmp	.L31
.L30:
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	leaq	0(,%rax,4), %rdx
	leaq	REF(%rip), %rax
	movl	(%rdx,%rax), %r8d
	movl	-8(%rbp), %eax
	movslq	%eax, %rcx
	movl	-4(%rbp), %eax
	movslq	%eax, %rdx
	movq	%rdx, %rax
	addq	%rax, %rax
	addq	%rdx, %rax
	addq	%rcx, %rax
	movl	-64(%rbp,%rax,4), %r9d
	movl	-8(%rbp), %edx
	movl	-4(%rbp), %eax
	leaq	.LC12(%rip), %rcx
	movl	%r8d, 32(%rsp)
	movl	%edx, %r8d
	movl	%eax, %edx
	call	__mingw_printf
.L31:
	addl	$1, -8(%rbp)
.L29:
	cmpl	$2, -8(%rbp)
	jle	.L32
	addl	$1, -4(%rbp)
.L28:
	cmpl	$2, -4(%rbp)
	jle	.L33
	movl	-24(%rbp), %edx
	movl	-20(%rbp), %eax
	leaq	.LC13(%rip), %rcx
	movl	%edx, %r8d
	movl	%eax, %edx
	call	__mingw_printf
	movl	-20(%rbp), %eax
	cmpl	-24(%rbp), %eax
	jne	.L34
	leaq	.LC14(%rip), %rax
	movq	%rax, %rcx
	call	puts
	jmp	.L35
.L34:
	leaq	.LC15(%rip), %rax
	movq	%rax, %rcx
	call	puts
.L35:
	movl	-20(%rbp), %eax
	cmpl	-24(%rbp), %eax
	setne	%al
	movzbl	%al, %eax
	addq	$112, %rsp
	popq	%rbp
	ret
	.seh_endproc
	.def	__main;	.scl	2;	.type	32;	.endef
	.ident	"GCC: (Rev7, Built by MSYS2 project) 16.2.0"
	.def	puts;	.scl	2;	.type	32;	.endef
	.def	putchar;	.scl	2;	.type	32;	.endef
