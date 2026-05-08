.global _hot_loop
.text
.align 64
_hot_loop:
    # Force Quorum loop directly into L1 cache
    prefetcht0 (%rdi)
    mov %rdi, %rax
    add $1, %rax
    ret
