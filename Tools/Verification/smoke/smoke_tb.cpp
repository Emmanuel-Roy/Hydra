// Toolchain smoke testbench: test infrastructure, not Ouroboros hardware. See README.md.
// Returns 0 when the kernel's running sums match a reference computed here,
// which is what C simulation and co-simulation report as pass or fail.
#include "smoke.hpp"
#include <cstdio>

int main()
{
	const int n = 256;
	hls::stream<sample_t> in;
	hls::stream<acc_t> out;
	long long expect[n];
	long long acc = 0;
	for (int i = 0; i < n; i++) {
		sample_t s;
		s.a = (i * 37) % 2001 - 1000;
		s.b = (i * 91) % 1777 - 888;
		acc += (long long)s.a.to_int() * s.b.to_int();
		expect[i] = acc;
		in.write(s);
	}
	smoke_top(in, out, n);
	int errors = 0;
	for (int i = 0; i < n; i++) {
		const long long got = out.read().to_int64();
		if (got != expect[i]) {
			if (errors < 5) std::printf("mismatch at %d: got %lld, expected %lld\n", i, got, expect[i]);
			errors++;
		}
	}
	std::printf("smoke: %s (%d mismatches of %d)\n", errors ? "FAIL" : "PASS", errors, n);
	return errors ? 1 : 0;
}
