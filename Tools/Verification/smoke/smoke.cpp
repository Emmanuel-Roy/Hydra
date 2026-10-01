// Toolchain smoke kernel: test infrastructure, not Ouroboros hardware. See README.md.
#include "smoke.hpp"

void smoke_top(hls::stream<sample_t> &in, hls::stream<acc_t> &out, int n)
{
#pragma HLS INTERFACE mode=axis port=in
#pragma HLS INTERFACE mode=axis port=out
#pragma HLS INTERFACE mode=s_axilite port=n
#pragma HLS INTERFACE mode=s_axilite port=return
	acc_t acc = 0;
	for (int i = 0; i < n; i++) {
#pragma HLS PIPELINE II=1
#pragma HLS LOOP_TRIPCOUNT min=16 max=1024
		const sample_t s = in.read();
		acc += (acc_t)s.a * (acc_t)s.b;
		out.write(acc);
	}
}
