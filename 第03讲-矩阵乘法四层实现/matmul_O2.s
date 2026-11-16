	.file	"matmul.c"
	.text
	.section .rdata,"dr"
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
	.section	.text.startup,"x"
	.p2align 4
	.globl	main
	.def	main;	.scl	2;	.type	32;	.endef
	.seh_proc	main
main:
	pushq	%r14
	.seh_pushreg	%r14
	pushq	%r13
	.seh_pushreg	%r13
	pushq	%r12
	.seh_pushreg	%r12
	pushq	%rbp
	.seh_pushreg	%rbp
	pushq	%rdi
	.seh_pushreg	%rdi
	pushq	%rsi
	.seh_pushreg	%rsi
	pushq	%rbx
	.seh_pushreg	%rbx
	subq	$96, %rsp
	.seh_stackalloc	96
	.seh_endprologue
	leaq	12+B(%rip), %rbx
	leaq	A(%rip), %rbp
	leaq	-12(%rbx), %r13
	leaq	12(%rbx), %r12
	call	__main
	leaq	48(%rsp), %rsi
	leaq	84(%rsp), %rdi
	movq	%rbp, %r8
	movq	%rsi, %rcx
.L2:
	movl	(%r8), %r11d
	movl	4(%r8), %r10d
	xorl	%eax, %eax
	movl	8(%r8), %r9d
.L3:
	movl	(%rbx,%rax), %edx
	movl	0(%r13,%rax), %r14d
	imull	%r10d, %edx
	imull	%r11d, %r14d
	addl	%r14d, %edx
	movl	(%r12,%rax), %r14d
	imull	%r9d, %r14d
	addl	%r14d, %edx
	movl	%edx, (%rcx,%rax)
	addq	$4, %rax
	cmpq	$12, %rax
	jne	.L3
	addq	$12, %rcx
	addq	$12, %r8
	cmpq	%rcx, %rdi
	jne	.L2
	movl	$3, %edx
	leaq	.LC0(%rip), %rcx
	leaq	36+A(%rip), %r12
	call	__mingw_printf
	leaq	.LC1(%rip), %rcx
	call	puts
.L6:
	leaq	.LC2(%rip), %rcx
	xorl	%ebx, %ebx
	call	__mingw_printf
.L5:
	movl	0(%rbp,%rbx,4), %edx
	leaq	.LC3(%rip), %rcx
	addq	$1, %rbx
	call	__mingw_printf
	cmpq	$3, %rbx
	jne	.L5
	leaq	.LC4(%rip), %rcx
	addq	$12, %rbp
	call	puts
	cmpq	%rbp, %r12
	jne	.L6
	leaq	.LC5(%rip), %rcx
	leaq	B(%rip), %rbp
	call	puts
	leaq	36(%rbp), %r12
.L8:
	leaq	.LC2(%rip), %rcx
	xorl	%ebx, %ebx
	call	__mingw_printf
.L7:
	movl	0(%rbp,%rbx,4), %edx
	leaq	.LC3(%rip), %rcx
	addq	$1, %rbx
	call	__mingw_printf
	cmpq	$3, %rbx
	jne	.L7
	leaq	.LC4(%rip), %rcx
	addq	$12, %rbp
	call	puts
	cmpq	%rbp, %r12
	jne	.L8
	leaq	.LC6(%rip), %rcx
	movq	%rsi, %rbp
	call	puts
.L10:
	leaq	.LC2(%rip), %rcx
	xorl	%ebx, %ebx
	call	__mingw_printf
.L9:
	movl	0(%rbp,%rbx,4), %edx
	leaq	.LC3(%rip), %rcx
	addq	$1, %rbx
	call	__mingw_printf
	cmpq	$3, %rbx
	jne	.L9
	leaq	.LC4(%rip), %rcx
	addq	$12, %rbp
	call	puts
	cmpq	%rdi, %rbp
	jne	.L10
	leaq	.LC7(%rip), %rcx
	movq	%rsi, %rbp
	call	__mingw_printf
.L11:
	xorl	%ebx, %ebx
.L12:
	movl	0(%rbp,%rbx,4), %edx
	leaq	.LC8(%rip), %rcx
	addq	$1, %rbx
	call	__mingw_printf
	cmpq	$3, %rbx
	jne	.L12
	addq	$12, %rbp
	cmpq	%rdi, %rbp
	jne	.L11
	movl	$10, %ecx
	leaq	REF(%rip), %rbp
	xorl	%r12d, %r12d
	xorl	%edi, %edi
	call	putchar
	movq	48(%rsp), %xmm1
	movq	56(%rsp), %xmm0
	leaq	.LC9(%rip), %rcx
	paddd	%xmm1, %xmm0
	movq	64(%rsp), %xmm1
	paddd	%xmm1, %xmm0
	movdqa	%xmm0, %xmm1
	psrlq	$32, %xmm1
	paddd	%xmm1, %xmm0
	movd	%xmm0, %edx
	addl	72(%rsp), %edx
	addl	76(%rsp), %edx
	addl	80(%rsp), %edx
	call	__mingw_printf
	leaq	.LC10(%rip), %rcx
	call	puts
.L14:
	xorl	%ebx, %ebx
.L17:
	movl	(%rsi,%rbx,4), %r9d
	movl	0(%rbp,%rbx,4), %eax
	cmpl	%eax, %r9d
	je	.L31
	movl	%eax, 32(%rsp)
	movl	%ebx, %r8d
	movl	%edi, %edx
	leaq	.LC12(%rip), %rcx
	call	__mingw_printf
.L16:
	addq	$1, %rbx
	cmpq	$3, %rbx
	jne	.L17
	addl	$1, %edi
	addq	$12, %rsi
	addq	$12, %rbp
	cmpl	$3, %edi
	jne	.L14
	movl	$9, %r8d
	movl	%r12d, %edx
	leaq	.LC13(%rip), %rcx
	call	__mingw_printf
	cmpl	$9, %r12d
	je	.L32
	leaq	.LC15(%rip), %rcx
	call	puts
.L20:
	xorl	%eax, %eax
	cmpl	$9, %r12d
	setne	%al
	addq	$96, %rsp
	popq	%rbx
	popq	%rsi
	popq	%rdi
	popq	%rbp
	popq	%r12
	popq	%r13
	popq	%r14
	ret
	.p2align 4,,10
	.p2align 3
.L31:
	movl	%r9d, 32(%rsp)
	movl	%ebx, %r8d
	movl	%edi, %edx
	addl	$1, %r12d
	leaq	.LC11(%rip), %rcx
	call	__mingw_printf
	jmp	.L16
.L32:
	leaq	.LC14(%rip), %rcx
	call	puts
	jmp	.L20
	.seh_endproc
	.section .rdata,"dr"
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
	.def	__main;	.scl	2;	.type	32;	.endef
	.ident	"GCC: (Rev7, Built by MSYS2 project) 16.2.0"
	.def	puts;	.scl	2;	.type	32;	.endef
	.def	putchar;	.scl	2;	.type	32;	.endef
