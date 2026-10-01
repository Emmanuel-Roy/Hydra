// Calibration testbench: test infrastructure, not Ouroboros hardware. See README.md.
//
// Assembles a small RV32I program (a two-pass assembler with label fixups),
// runs it on core_top, and checks what it stored against values computed
// here. Exercises: stores then loads (a load-use stall), backward branches,
// a call and return (JAL/JALR), byte stores with signed and unsigned loads
// back to back, halfwords, LUI. Prints cycles, instructions and CPI.
#include "core.hpp"
#include <cstdio>
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace {

struct Asm {
	std::vector<uint32_t> code;
	std::map<std::string, int> labels;
	struct Fix { int at; std::string label; char kind; };
	std::vector<Fix> fixes;

	void label(const std::string &l) { labels[l] = (int)code.size() * 4; }
	void r(int f7, int rs2, int rs1, int f3, int rd, int op) { code.push_back(f7 << 25 | rs2 << 20 | rs1 << 15 | f3 << 12 | rd << 7 | op); }
	void i(int imm, int rs1, int f3, int rd, int op) { code.push_back((uint32_t)(imm & 0xFFF) << 20 | rs1 << 15 | f3 << 12 | rd << 7 | op); }
	void s(int imm, int rs2, int rs1, int f3) { code.push_back((uint32_t)((imm >> 5) & 0x7F) << 25 | rs2 << 20 | rs1 << 15 | f3 << 12 | (imm & 0x1F) << 7 | 0x23); }
	void u(uint32_t imm20, int rd, int op) { code.push_back(imm20 << 12 | rd << 7 | op); }
	void b(int f3, int rs1, int rs2, const std::string &l) { fixes.push_back({(int)code.size(), l, 'B'}); code.push_back(rs2 << 20 | rs1 << 15 | f3 << 12 | 0x63); }
	void jal(int rd, const std::string &l) { fixes.push_back({(int)code.size(), l, 'J'}); code.push_back(rd << 7 | 0x6F); }

	// Mnemonics used below.
	void addi(int rd, int rs1, int imm) { i(imm, rs1, 0, rd, 0x13); }
	void slli(int rd, int rs1, int sh) { i(sh, rs1, 1, rd, 0x13); }
	void add(int rd, int rs1, int rs2) { r(0, rs2, rs1, 0, rd, 0x33); }
	void lw(int rd, int rs1, int imm) { i(imm, rs1, 2, rd, 0x03); }
	void lb(int rd, int rs1, int imm) { i(imm, rs1, 0, rd, 0x03); }
	void lbu(int rd, int rs1, int imm) { i(imm, rs1, 4, rd, 0x03); }
	void lh(int rd, int rs1, int imm) { i(imm, rs1, 1, rd, 0x03); }
	void sw(int rs2, int rs1, int imm) { s(imm, rs2, rs1, 2); }
	void sh(int rs2, int rs1, int imm) { s(imm, rs2, rs1, 1); }
	void sb(int rs2, int rs1, int imm) { s(imm, rs2, rs1, 0); }
	void jalr(int rd, int rs1, int imm) { i(imm, rs1, 0, rd, 0x67); }
	void ecall() { code.push_back(0x73); }

	void finish()
	{
		for (const Fix &f : fixes) {
			const int off = labels.at(f.label) - f.at * 4;
			uint32_t &w = code[f.at];
			if (f.kind == 'B')
				w |= ((off >> 12) & 1) << 31 | ((off >> 5) & 0x3F) << 25 | ((off >> 1) & 0xF) << 8 | ((off >> 11) & 1) << 7;
			else
				w |= ((off >> 20) & 1) << 31 | ((off >> 1) & 0x3FF) << 21 | ((off >> 11) & 1) << 20 | ((off >> 12) & 0xFF) << 12;
		}
	}
};

constexpr int BLT = 4, BEQ = 0;

}  // namespace

int main()
{
	Asm a;
	// 1. store 3i+1 for i < 16 at word i, then sum them back (load-use stall)
	a.addi(2, 0, 16);
	a.addi(3, 0, 0);
	a.label("store");
	a.slli(4, 3, 2);
	a.slli(5, 3, 1);
	a.add(5, 5, 3);
	a.addi(5, 5, 1);
	a.sw(5, 4, 0);
	a.addi(3, 3, 1);
	a.b(BLT, 3, 2, "store");
	a.addi(3, 0, 0);
	a.addi(6, 0, 0);
	a.label("sum");
	a.slli(4, 3, 2);
	a.lw(5, 4, 0);
	a.add(6, 6, 5);
	a.addi(3, 3, 1);
	a.b(BLT, 3, 2, "sum");
	a.sw(6, 0, 256);
	// 2. fib(20), as a call and a return
	a.addi(10, 0, 20);
	a.jal(1, "fib");
	a.sw(10, 0, 260);
	// 3. a byte store, read back signed and unsigned, back to back
	a.addi(7, 0, -2);
	a.sb(7, 0, 264);
	a.lb(8, 0, 264);
	a.lbu(9, 0, 264);
	a.sw(8, 0, 268);
	a.sw(9, 0, 272);
	// 4. LUI + ADDI
	a.u(0x12345, 11, 0x37);
	a.addi(11, 11, 0x678);
	a.sw(11, 0, 276);
	// 5. a halfword
	a.addi(12, 0, -1234);
	a.sh(12, 0, 280);
	a.lh(13, 0, 280);
	a.sw(13, 0, 284);
	a.ecall();
	// fib(n) in x10: iterative
	a.label("fib");
	a.addi(12, 0, 0);
	a.addi(13, 0, 1);
	a.label("floop");
	a.b(BEQ, 10, 0, "fdone");
	a.add(14, 12, 13);
	a.addi(12, 13, 0);
	a.addi(13, 14, 0);
	a.addi(10, 10, -1);
	a.jal(0, "floop");
	a.label("fdone");
	a.addi(10, 12, 0);
	a.jalr(0, 1, 0);
	a.finish();

	static word_t imem[IMEM_WORDS];
	static byte_t d0[DMEM_WORDS], d1[DMEM_WORDS], d2[DMEM_WORDS], d3[DMEM_WORDS];
	for (size_t k = 0; k < a.code.size(); k++) imem[k] = a.code[k];

	ap_uint<32> cycles, instret;
	bool halted;
	core_top(imem, d0, d1, d2, d3, 100000, cycles, instret, halted);

	auto word = [&](int addr) -> uint32_t {
		const int w = addr / 4;
		return (uint32_t)d0[w] | (uint32_t)d1[w] << 8 | (uint32_t)d2[w] << 16 | (uint32_t)d3[w] << 24;
	};
	uint32_t sum = 0;
	for (int k = 0; k < 16; k++) sum += 3 * k + 1;
	uint32_t f0 = 0, f1 = 1;
	for (int k = 0; k < 20; k++) { const uint32_t t = f0 + f1; f0 = f1; f1 = t; }

	struct Check { const char *what; int addr; uint32_t want; };
	const Check checks[] = {
		{"sum of 3i+1, i<16", 256, sum},
		{"fib(20) by call", 260, f0},
		{"lb of 0xFE", 268, (uint32_t)-2},
		{"lbu of 0xFE", 272, 254},
		{"lui+addi", 276, 0x12345678},
		{"lh of -1234", 284, (uint32_t)-1234},
	};
	int errors = 0;
	for (const Check &c : checks) {
		const uint32_t got = word(c.addr);
		if (got != c.want) {
			std::printf("FAIL %s: got 0x%08x, want 0x%08x\n", c.what, got, c.want);
			errors++;
		}
	}
	if (!halted) { std::printf("FAIL: no ecall retired in 100000 cycles\n"); errors++; }
	std::printf("calibration rv32i: %s -- %u cycles, %u instructions, CPI %.3f\n", errors ? "FAIL" : "PASS",
	            (unsigned)cycles, (unsigned)instret, instret ? (double)cycles / (double)instret : 0.0);
	return errors ? 1 : 0;
}
