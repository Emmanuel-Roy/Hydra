// Toolchain smoke kernel: test infrastructure, not Ouroboros hardware. See README.md.
#pragma once
#include <ap_int.h>
#include <hls_stream.h>

struct sample_t {
	ap_int<16> a;
	ap_int<16> b;
};
typedef ap_int<48> acc_t;

void smoke_top(hls::stream<sample_t> &in, hls::stream<acc_t> &out, int n);
