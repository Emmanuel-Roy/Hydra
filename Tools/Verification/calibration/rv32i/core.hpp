// Calibration core: test infrastructure, not Ouroboros hardware. See README.md.
#pragma once
#include <ap_int.h>

typedef ap_uint<32> word_t;
typedef ap_uint<8> byte_t;

constexpr int IMEM_WORDS = 1024;   // 4 KiB of instructions
constexpr int DMEM_WORDS = 1024;   // 4 KiB of data, as four byte lanes

// Runs the program in imem from pc 0 until an ecall retires or max_cycles
// pass. Data memory is four byte lanes so a byte or halfword store needs no
// read-modify-write. Reports the cycles taken and instructions retired.
void core_top(const word_t imem[IMEM_WORDS],
              byte_t dmem0[DMEM_WORDS], byte_t dmem1[DMEM_WORDS],
              byte_t dmem2[DMEM_WORDS], byte_t dmem3[DMEM_WORDS],
              ap_uint<32> max_cycles, ap_uint<32> &cycles, ap_uint<32> &instret, bool &halted);
