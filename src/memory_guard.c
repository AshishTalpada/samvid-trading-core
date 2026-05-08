#include <sys/mman.h>
#include <unistd.h>

void lock_instruction_cache(void* function_ptr, size_t size) {
    // Use mprotect to lock executable memory as PROT_READ | PROT_EXEC (NX Bit enforcement)
    mprotect(function_ptr, size, PROT_READ | PROT_EXEC);
}
