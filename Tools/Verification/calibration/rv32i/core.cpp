// Calibration core: test infrastructure, not Ouroboros hardware. See README.md.
//
// A five-stage RV32I pipeline written as docs/hls-coding-standard.md asks:
// one loop at II=1 whose body is one clock cycle, explicit stage registers,
// the stages evaluated write-back first, a stall vector computed before any
// stage register updates, forwarding by comparing register indices. It exists
// to measure what HLS costs for this style -- LUTs, flip-flops, Fmax, and
// whether II=1 holds -- on the target, before the real core is designed.
#include "core.hpp"

namespace {

enum Op { OP_ALU, OP_LUI, OP_AUIPC, OP_JAL, OP_JALR, OP_BRANCH, OP_LOAD, OP_STORE, OP_ECALL, OP_NOP };

struct IfId {
	bool valid;
	ap_uint<32> pc, instr;
};

struct IdEx {
	bool valid;
	ap_uint<32> pc, rs1v, rs2v, imm;
	ap_uint<5> rs1, rs2, rd;
	ap_uint<4> op;
	ap_uint<3> f3;
	bool alt;       // funct7 bit 5: SUB, SRA
	bool imm_b;     // the ALU's second operand is the immediate
	bool wb;
};

struct ExMem {
	bool valid;
	ap_uint<32> value, store;   // ALU result or address; store data
	ap_uint<5> rd;
	ap_uint<3> f3;
	bool load, storeop, wb, ecall;
};

struct MemWb {
	bool valid;
	ap_uint<32> value;
	ap_uint<5> rd;
	bool wb, ecall;
};

ap_uint<32> sext(ap_uint<32> v, int bits)
{
	const int shift = 32 - bits;
	return (ap_uint<32>)(((ap_int<32>)(v << shift)) >> shift);
}

ap_uint<32> alu(ap_uint<3> f3, bool alt, ap_uint<32> a, ap_uint<32> b)
{
	const ap_uint<5> sh = b.range(4, 0);
	switch (f3) {
	case 0: return alt ? (ap_uint<32>)(a - b) : (ap_uint<32>)(a + b);
	case 1: return a << sh;
	case 2: return (ap_int<32>)a < (ap_int<32>)b ? 1 : 0;
	case 3: return a < b ? 1 : 0;
	case 4: return a ^ b;
	case 5: return alt ? (ap_uint<32>)((ap_int<32>)a >> sh) : (ap_uint<32>)(a >> sh);
	case 6: return a | b;
	default: return a & b;
	}
}

bool branch_taken(ap_uint<3> f3, ap_uint<32> a, ap_uint<32> b)
{
	switch (f3) {
	case 0: return a == b;
	case 1: return a != b;
	case 4: return (ap_int<32>)a < (ap_int<32>)b;
	case 5: return (ap_int<32>)a >= (ap_int<32>)b;
	case 6: return a < b;
	case 7: return a >= b;
	default: return false;
	}
}

} // namespace

void core_top(const word_t imem[IMEM_WORDS],
              byte_t dmem0[DMEM_WORDS], byte_t dmem1[DMEM_WORDS],
              byte_t dmem2[DMEM_WORDS], byte_t dmem3[DMEM_WORDS],
              ap_uint<32> max_cycles, ap_uint<32> &cycles, ap_uint<32> &instret, bool &halted)
{
	ap_uint<32> rf[32];
#pragma HLS ARRAY_PARTITION variable=rf type=complete
	for (int i = 0; i < 32; i++) rf[i] = 0;

	IfId ifid = {};
	IdEx idex = {};
	ExMem exmem = {};
	MemWb memwb = {};
	ap_uint<32> pc = 0, retired = 0, cycle = 0;
	bool done = false;
	bool fetching = true;   // until an ecall reaches EX: nothing after it may run

	for (cycle = 0; cycle < max_cycles && !done; cycle++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=dmem0 type=inter false
#pragma HLS DEPENDENCE variable=dmem1 type=inter false
#pragma HLS DEPENDENCE variable=dmem2 type=inter false
#pragma HLS DEPENDENCE variable=dmem3 type=inter false
		// ---- WB: first, so ID below reads the value written this cycle ----
		if (memwb.valid) {
			if (memwb.wb && memwb.rd != 0) rf[memwb.rd] = memwb.value;
			retired++;
			if (memwb.ecall) done = true;
		}

		// ---- MEM ----
		MemWb mw_next = {};
		if (exmem.valid) {
			const ap_uint<32> addr = exmem.value;
			const ap_uint<10> w = addr.range(11, 2);
			const ap_uint<2> lane = addr.range(1, 0);
			ap_uint<32> v = exmem.value;
			if (exmem.load) {
				const ap_uint<32> word = (ap_uint<8>(dmem3[w]), ap_uint<8>(dmem2[w]), ap_uint<8>(dmem1[w]), ap_uint<8>(dmem0[w]));
				const ap_uint<32> shifted = word >> (lane * 8);
				switch (exmem.f3) {
				case 0: v = sext(shifted.range(7, 0), 8); break;
				case 1: v = sext(shifted.range(15, 0), 16); break;
				case 4: v = shifted.range(7, 0); break;
				case 5: v = shifted.range(15, 0); break;
				default: v = word; break;
				}
			}
			if (exmem.storeop) {
				const ap_uint<32> d = exmem.store << (lane * 8);
				const ap_uint<4> be = exmem.f3 == 0 ? (ap_uint<4>)(1 << lane)
				                    : exmem.f3 == 1 ? (ap_uint<4>)(3 << lane) : (ap_uint<4>)0xF;
				if (be[0]) dmem0[w] = d.range(7, 0);
				if (be[1]) dmem1[w] = d.range(15, 8);
				if (be[2]) dmem2[w] = d.range(23, 16);
				if (be[3]) dmem3[w] = d.range(31, 24);
			}
			mw_next = {true, v, exmem.rd, exmem.wb, exmem.ecall};
		}

		// ---- EX, with forwarding from the instructions in MEM and WB ----
		ExMem em_next = {};
		bool redirect = false;
		ap_uint<32> target = 0;
		if (idex.valid) {
			ap_uint<32> a = idex.rs1v, b = idex.rs2v;
			if (memwb.valid && memwb.wb && memwb.rd != 0 && memwb.rd == idex.rs1) a = memwb.value;
			if (memwb.valid && memwb.wb && memwb.rd != 0 && memwb.rd == idex.rs2) b = memwb.value;
			if (exmem.valid && exmem.wb && !exmem.load && exmem.rd != 0 && exmem.rd == idex.rs1) a = exmem.value;
			if (exmem.valid && exmem.wb && !exmem.load && exmem.rd != 0 && exmem.rd == idex.rs2) b = exmem.value;
			ap_uint<32> r = 0;
			switch (idex.op) {
			case OP_ALU: r = alu(idex.f3, idex.alt && !(idex.imm_b && idex.f3 == 0), a, idex.imm_b ? idex.imm : b); break;
			case OP_LUI: r = idex.imm; break;
			case OP_AUIPC: r = idex.pc + idex.imm; break;
			case OP_JAL: r = idex.pc + 4; redirect = true; target = idex.pc + idex.imm; break;
			case OP_JALR: r = idex.pc + 4; redirect = true; target = (a + idex.imm) & ~(ap_uint<32>)1; break;
			case OP_BRANCH: if (branch_taken(idex.f3, a, b)) { redirect = true; target = idex.pc + idex.imm; } break;
			case OP_LOAD: case OP_STORE: r = a + idex.imm; break;
			default: break;
			}
			em_next = {true, r, b, idex.rd, idex.f3, idex.op == OP_LOAD, idex.op == OP_STORE, idex.wb, idex.op == OP_ECALL};
		}

		// ---- ID: decode, read the register file, detect a load-use hazard ----
		IdEx ie_next = {};
		bool stall = false;
		if (ifid.valid) {
			const ap_uint<32> in = ifid.instr;
			const ap_uint<7> opc = in.range(6, 0);
			const ap_uint<5> rd = in.range(11, 7), rs1 = in.range(19, 15), rs2 = in.range(24, 20);
			const ap_uint<3> f3 = in.range(14, 12);
			const ap_uint<32> imm_i = sext(in.range(31, 20), 12);
			const ap_uint<32> imm_s = sext((in.range(31, 25), in.range(11, 7)), 12);
			const ap_uint<32> imm_b = sext((in[31], in[7], in.range(30, 25), in.range(11, 8), ap_uint<1>(0)), 13);
			const ap_uint<32> imm_u = (in.range(31, 12), ap_uint<12>(0));
			const ap_uint<32> imm_j = sext((in[31], in.range(19, 12), in[20], in.range(30, 21), ap_uint<1>(0)), 21);
			IdEx d = {true, ifid.pc, rf[rs1], rf[rs2], 0, rs1, rs2, rd, OP_NOP, f3, (bool)in[30], false, false};
			switch (opc) {
			case 0x33: d.op = OP_ALU; d.wb = true; break;
			case 0x13: d.op = OP_ALU; d.imm = imm_i; d.imm_b = true; d.wb = true; break;
			case 0x37: d.op = OP_LUI; d.imm = imm_u; d.wb = true; break;
			case 0x17: d.op = OP_AUIPC; d.imm = imm_u; d.wb = true; break;
			case 0x6F: d.op = OP_JAL; d.imm = imm_j; d.wb = true; break;
			case 0x67: d.op = OP_JALR; d.imm = imm_i; d.wb = true; break;
			case 0x63: d.op = OP_BRANCH; d.imm = imm_b; break;
			case 0x03: d.op = OP_LOAD; d.imm = imm_i; d.wb = true; break;
			case 0x23: d.op = OP_STORE; d.imm = imm_s; break;
			case 0x73: d.op = OP_ECALL; break;
			default: break;
			}
			// A load in EX whose result this instruction needs: wait a cycle.
			const bool uses_rs2 = opc == 0x33 || opc == 0x63 || opc == 0x23;
			stall = idex.valid && idex.op == OP_LOAD && idex.rd != 0
			        && (idex.rd == rs1 || (uses_rs2 && idex.rd == rs2));
			ie_next = d;
		}

		// ---- IF ----
		const IfId if_next = {fetching, pc, imem[pc.range(11, 2)]};
		const bool ecall_in_ex = idex.valid && idex.op == OP_ECALL;

		// ---- update the stage registers, the taken branch flushing behind it ----
		memwb = mw_next;
		exmem = em_next;
		if (ecall_in_ex) {
			// The end of the program: flush what was fetched behind it.
			idex.valid = false;
			ifid.valid = false;
			fetching = false;
		} else if (redirect) {
			idex.valid = false;
			ifid.valid = false;
			pc = target;
		} else if (stall) {
			idex.valid = false;         // a bubble; IF/ID and pc hold
		} else {
			idex = ie_next;
			ifid = if_next;
			pc = pc + 4;
		}
		if (done) {
			exmem.valid = false;
			idex.valid = false;
			ifid.valid = false;
		}
	}
	cycles = cycle;
	instret = retired;
	halted = done;
}
