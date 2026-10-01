# KV260 (K26 SOM / XCK26) as a PL-only soft RISC-V Linux platform

Primary sources were downloaded and searched directly as text: DS987 v1.5 (Jan 30, 2024), UG1089 v1.3 (May 14, 2024), UG1085 v1.8 (Aug 3, 2018; old revision, but the boot and PS-PL architecture has not changed). Source URLs:
- DS987 (K26 SOM data sheet) — https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf (mirror: https://www.mouser.com/datasheet/2/903/ds987_k26_som-2329045.pdf)
- UG1089 (KV260 user guide) — https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf
- UG1085 (ZynqMP TRM) — https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf

## Q1. Exact PL resources of the XCK26 on the KV260 SOM

### Takeaway
The XCK26 has about the same PL as a ZU5EV: 117,120 LUTs, 234,240 FFs, 1,248 DSP slices, 144 BRAM36 (5.1 Mb), 64 URAM (18 Mb at 288 Kb each) and 4 GTH. It is a -2 speed grade part, but it runs at the low-voltage VCCINT of 0.72 V (-2LE/-2LI), so its timing is slower than a standard -2 part at 0.85 V.

### Cited Findings
- The part is XCK26-SFVC784-2LV-C/I, "a custom-built Zynq UltraScale+ MPSoC that runs optimally (and exclusively) on the SOM" — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- Table 5, "PL Resources": 256,200 system logic cells; 234,240 CLB flip-flops; 117,120 CLB LUTs; 3.5 Mb distributed RAM; 144 block RAMs (36 Kb); 5.1 Mb block RAM; 64 UltraRAM blocks ("288 Kb dual-port, 72-bit-wide memory with error correction"); 1,248 DSP slices ("27 x 18 signed multiplier with 48-bit adder/accumulator", i.e. DSP48E2); 4 GTH transceivers (up to 12.5 Gb/s); 1 video codec (VCU, H.264/H.265); 69 HDIO; 116 HPIO — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf). The table is scrambled in the PDF text; I matched values to rows using the row descriptions, and they agree with the [ikwzm/Mouser search summary](https://github.com/ikwzm/ArgSort-Kv260).
- "The K26 SOM is built with the XCK26-SFVC784-2LV device; which has a -2 speed grade and is an LV device." The commercial K26C uses "-2LE (VCCINT = 0.72V)", and DS925 -2 at 0.72 V timing applies. The industrial K26I uses -2LI at 0.72 V, which is "not specified in" DS925, so DS987 gives its own tables. Example: BRAM FMAX_FIFO is 516 MHz and BRAM ECC without pipeline is 460 MHz at -2LI — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- PL I/O banks: HPIO banks 64/65/66 and HDIO banks 43/44/45. The SOM240 connector carries 21+24+24 HDIO and the HPIO counts listed in DS987 Table 3. There is one GTH quad (4 lanes) and one PS-GTR bank 505 (4 lanes, up to 6.0 Gb/s) — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- Junction temperature range: 0–85 °C (commercial) and −40–100 °C (industrial) — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- Clocking: the KV260 has no on-board clock source for the PL independent of the PS. The LiteX platform file says "there are no on-board clock sources for PL when PS is not used" and offers a clock-capable Pmod pin (HDA16_CC, pin E12) as an untested alternative — [litex-boards xilinx_kv260 platform](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/platforms/xilinx_kv260.py). The clocks on the board are PS_REF_CLK at 33.33 MHz plus PS-GTR reference clocks (27 MHz DP, 26 MHz USB, 125 MHz SATA ref). PL clocks come from the PS (pl_clk0, typically 100 MHz after PetaLinux/FSBL init) — [tomverbeure/kv260_bringup](https://github.com/tomverbeure/kv260_bringup)

### Inferences
- A single-hart RVA23S64 out-of-order or wide in-order core plus a systolic array must share about 117k LUTs. For scale: a Rocket single-core RV64GC with FPU typically uses about 40–60k LUTs, and CVA6 about 40–70k LUTs. (These figures are from my general knowledge and were not sourced in this pass. Verify them in the soft-core research.) RVA23 also mandates the V extension, which adds a lot. Taken together, this points to 117k LUTs being tight.
- 1,248 DSP48E2 is the main budget for the systolic array. INT8 packing (two INT8 MACs per DSP48E2) gives about 2,496 MAC/cycle at most; at 250–300 MHz that is about 0.6–0.75 TOPS INT8 theoretical. This is arithmetic, not a measured figure.
- The 0.72 V speed grade means soft-CPU Fmax will be lower than published numbers for standard -2 ZU+ parts.

### Gaps
- I did not confirm the exact BUFG, MMCM and PLL counts for the XCK26. The ZU5EV-class numbers are probably 4 MMCM/8 PLL in 4 clock regions, but this is unconfirmed. See the DS891 product table.

## Q2. Memory: DDR4 size, width, speed and bandwidth; how the PL reaches it

### Takeaway
All 4 GB of DDR4 (64-bit, 2400 MT/s, non-ECC per the DS987 wording, about 19.2 GB/s theoretical) hangs off the PS DDR controller. The KV260 has no PL-attached DRAM. The PL reaches DDR only through PS-PL AXI slave ports (HP0–3, HPC0/1, ACP, ACE, LPD), which are 32/64/128-bit on the PL side and 128-bit on the PS side. In practice one port reaches roughly 2.5–3 GB/s.

### Cited Findings
- "4 GB 64-bit wide, 2400 Mb/s memory" on the SOM. DS987 Table 3 lists "SOM DDR4 memory" on PS MIO bank 504, which is the PS DDR interface — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- Theoretical peak for ZynqMP 64-bit DDR4-2400: 2400 MT/s × 8 B = 19,200 MB/s — [search summary of ResearchGate "Unexpected Diversity: Quantitative Memory Analysis for Zynq UltraScale+"](https://www.researchgate.net/publication/336714879_Unexpected_Diversity_Quantitative_Memory_Analysis_for_Zynq_UltraScale_Systems)
- The physical address map as used by LiteX on the KV260 has two DDR windows: 0x0000_0000–0x7FFF_FFFF (2 GB) and 0x8_0000_0000–0x8_7FFF_FFFF (2 GB) — [litex-boards xilinx_kv260 target](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)
- PS-PL ports (TRM Table 2-13):
  - S_AXI_HP{0:3}_FPD: "non-coherent paths from PL to FPD main switch and DDR"
  - S_AXI_HPC{0,1}_FPD: "I/O coherent with CCI"
  - S_AXI_ACP_FPD: "I/O coherent with L2 cache allocation"
  - S_AXI_ACE_FPD: "two-way coherent"
  - S_AXI_LPD: "non-coherent path from PL to IOP in LPD"
  - M_AXI_HPM0/1_FPD and M_AXI_HPM0_LPD: PS-master to PL
  — [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- "The 32, 64, and 128-bit programmable logic interfaces are programmable; the PS-side AXI interface is always 128 bits." HP ports connect directly to DDR controller XPI ports ("high throughput and relatively low-latency access from the PL directly to the DDR"). HPC ports go through the CCI and "have a longer latency to DDR". The ZynqMP physical address space is 40 bits — [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- Measured: HP0 peaks at about 3 GB/s, and reads get at least 20% more throughput than writes — [ResearchGate summary, "Unexpected Diversity"](https://www.researchgate.net/publication/336714879_Unexpected_Diversity_Quantitative_Memory_Analysis_for_Zynq_UltraScale_Systems). Treat this as a search-snippet figure; I did not read the full paper.
- On an Ultra96-V2 (ZU3EG, DDR4) with 128-bit ports at 250 MHz (4 GB/s theoretical per port), the HP port reached about 60–70% utilisation for large transfers. HP latency was "quite high and also quite variable". ACP gave the best utilisation for transfers under L2 size — [j-marjanovic.io](https://j-marjanovic.io/exploring-the-ps-pl-axi-interfaces-on-zynq-ultrascale-mpsoc.html)
- The K26 has no PL-side DDR. The only other memory on the SOM is 512 Mb QSPI, 16 GB eMMC and a 64 Kb EEPROM, all PS-attached — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf). Large on-chip memory is limited to 64 URAM (18 Mb ≈ 2.25 MB) plus 5.1 Mb BRAM.

### Inferences
- A soft CPU and an LLM accelerator would reach DDR through 4 HP + 2 HPC ports. The aggregate could approach the 19.2 GB/s DDRC ceiling only with several parallel 128-bit masters at about 250–300 MHz. The realistic total is probably about 8–12 GB/s. That figure is an inference from about 3 GB/s per port, and the PS DDR controller's QoS and efficiency limits are not measured here.
- For LLM inference, which is memory-bandwidth-bound, about 10 GB/s and 4 GB of capacity limit model size. A 1B-parameter INT4 model is about 0.5 GB and would give about 20 tok/s at most, bandwidth-bound. This is arithmetic only.
- The memory map is split (2 GB low, 2 GB at 0x8_0000_0000). The RISC-V SoC's device tree and its interconnect remap must handle this, or the design must use only the low 2 GB, or remap in PL.

### Gaps
- I found no measured aggregate multi-port PL→DDR bandwidth specifically on the K26/KV260.
- DDR4 ECC: DS987 does not mention ECC for the SOM DDR. I believe it is non-ECC but have not confirmed it.

## Q3. Boot: can the PL be configured and DDR brought up without ARM code? Who runs what?

### Takeaway
Standalone (non-JTAG) boot of a ZynqMP always runs two triple-redundant MicroBlaze-class controllers: the PMU ROM and the CSU BootROM. The CSU BootROM then always hands off to an FSBL that runs on either an A53 or an R5. The FSBL (psu_init) is what sets the PS PLLs, pl_clk, MIO and the DDR controller, and it loads the bitstream through PCAP. So "no ARM code at all" is achievable only in JTAG-tethered bring-up, where XSCT writes psu_init registers through the debug access port and configures the PL over JTAG. For a self-booting laptop, a minimal ARM FSBL is unavoidable. The R5 can be chosen instead of the A53, and after the FSBL the core can be parked in WFE/WFI with no OS. The stock Kria boot flow (ImgSel → FSBL → PMUFW → TF-A → U-Boot → Linux on the A53s) must be replaced.

### Cited Findings
- PMU sequence after POR: "the PMU is brought out of reset by the POR, which is then followed by PMU ROM execution". It initialises SYSMON and PLLs, clears PMU/CSU RAM, validates supplies, and "releases the CSU reset" — [UG1085 ch. 11](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- CSU sequence: "Initialize OCM. Determine the boot mode... The CSU continues by loading the FSBL in OCM for execution by either the RPU and APU. Then, the CSU loads the PMU user firmware (PMU FW) into the PMU RAM". Also: "The PMU FW is required in most systems and must be present for the Xilinx-based FSBL and system software." The CSU is "a triple-redundant secure processor" containing the PCAP — [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- "The boot header defines... the processor MPCore to execute the FSBL", which is A53 or R5 — [UG1085 via search summary](https://www.scribd.com/document/872458264/Ug1085-Zynq-Ultrascale-Trm); consistent with the [Bootgen UG1283](https://docs.amd.com/api/khub/documents/6NVD9vTkjlLGHfCRFC9FNQ/content)
- "After executing CSU ROM code, the CSU hands off the control to the first-stage boot loader (FSBL). The FSBL uses the PCAP interface to configure the PL with the bitstream." The PCAP sequence is register writes (csu.pcap_reset, pcap_ctrl, pcap_prog, and a PMU power-up request if the PL is off). Any bus master that can reach CSU registers could do this in principle — [UG1085 "Load the PL Bitstream"](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- The FSBL "configures the FPGA with hardware bitstream (if it exists) and loads the OS Image or Standalone Image or 2nd Stage Boot Loader... and takes A53/R5 out of reset". The FSBL includes psu_init.{c,h}, which covers "pin muxes, DDR memory configuration, etc." DDR ECC init is done in the FSBL — [AMD wiki FSBL](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842019/FSBL) (search snippet; the page body did not render)
- Boot modes include PS JTAG (mode 0000), QSPI, SD, eMMC, USB 2.0 and NAND — [UG1085 Table 11-1](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- JTAG alternative: Vivado exports psu_init.tcl, which XSCT can `source` and run (`psu_init`). It performs about 500 register writes covering PLL, clock, DDR and MIO init, with no FSBL — [Trenz MPSoC Debug wiki / AMD wiki JTAG-boot script (search summaries)](https://wiki.trenz-electronic.de/display/PD/MPSoC+Debug), [AMD wiki: TCL script for JTAG boot](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/84444479/TCL+script+to+auto-generate+a+jtag+boot+script+based+on+HDF+file+for+Zynq+Ultrascale)
- KV260 stock boot: the boot mode is strapped to QSPI32. QSPI BOOT.BIN contains FSBL, PMU firmware, TF-A ("Arm trusted firmware") and U-Boot. U-Boot hands off to the SD card (Linux). QSPI holds A/B copies plus a recovery tool — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- The Image Selector (ImgSel) "is a small baremetal application running out of OCM after a POR/SRST" that picks the A/B BOOT.BIN. The QSPI map has Image A at 0x0020_0000 and Image B at 0x00F8_0000, with "space for larger images (PL - 8MB, RPU - 2MB)" — [Kria Boot FW overview](https://xilinx.github.io/kria-apps-docs/bootfw/build/html/docs/bootfw_overview.html)
- DS987 pin notes: MIO32–34 are reserved for the PMU, and MIO34 (power management) is implemented on the K26 — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- "If you booted the board without an SDCard and without loading a barebones FW somehow, then the PL part isn't activated" (on the KV260) — [tomverbeure/kv260_bringup](https://github.com/tomverbeure/kv260_bringup)
- LiteX's KV260 target uses the PS (A53 "zynqmp" CPU type) and PS clock by default. It references the external PMU firmware builder (lucaceresoli/zynqmp-pmufw-builder) and xsct scripts — [litex-boards xilinx_kv260 target](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)

### Who runs what (summary)
| Stage | Processor | Avoidable? |
|---|---|---|
| PMU ROM | PMU (triple-redundant MicroBlaze, LPD) | No (hardwired) — [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf) |
| CSU BootROM | CSU (triple-redundant secure processor) | No (hardwired) — [UG1085](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf) |
| ImgSel (Kria only) | A53 or R5 from OCM (the doc says "baremetal app in OCM"; which core is not stated) | Yes, replace it with your own BOOT.BIN at the QSPI base or boot from SD by mode pins |
| FSBL (psu_init: PLLs, pl_clk, MIO, DDRC; PCAP bitstream load) | A53-0 or R5-0, selected in the boot header | No for standalone boot. Only JTAG/XSCT avoids it. |
| PMU firmware | PMU MicroBlaze | "Required in most systems". Probably omittable for a minimal flow, but unverified. |
| TF-A, U-Boot, Linux | A53 | Yes (not needed for a PL-only system) |

### Inferences
- The strictest honest wording of the owner's goal is: "No ARM core runs an OS or any user software. A ~tens-of-KB FSBL runs once on the R5 (or A53) at power-on to set clocks/DDR/MIO and load the PL bitstream, then parks in WFI. The PMU and CSU microcontrollers run their fixed ROMs." There is no hardware path in which the boot ROM configures DDR or the PL by itself.
- A more extreme, unverified option: a tiny FSBL that only does clocks, PL power and PCAP bitstream load, after which the RISC-V in the PL replays the psu_init DDR register writes through S_AXI_LPD or HPM-reachable register space. Two problems make this risky. The PL needs a clock before DDR init, and on the KV260 that comes from the PS (pl_clk) or an external Pmod clock. DDR training (PHY init, ZynqMP DDR PHY "PIR" training) is done by psu_init code and would need to be ported. This is not recommended.
- Parking: once the FSBL hands off to nothing (or to a one-instruction WFI loop on R5-0), the A53 cluster stays in reset by default (the FSBL only releases cores it loads images for). This is an inference from the FSBL description; the APU/FPD could also be powered down through PMU requests to save power.
- Because the PL clock and the DDR controller depend on the PS, the PS (LPD and FPD power domains, DDRC, CCI/FPD switch for HP ports) must stay powered and configured the whole time. "Not using the CPU cores" does not mean "not using the PS".

### Gaps
- I did not find an AMD statement that explicitly says "FSBL is always required". The forum thread "Zynq UltraScale+ MPSoC - FSBL always required?" did not render — [AMD adaptive support](https://adaptivesupport.amd.com/s/question/0D52E00006iHlb0SAC/zynq-ultrascale-mpsoc-fsbl-always-required?language=en_US). The conclusion above follows from the TRM boot sequence.
- I did not confirm whether a BOOT.BIN without a PMUFW partition boots cleanly with the 2022+ FSBL.
- I did not confirm which processor runs Kria's ImgSel.
- UG1137 (Software Developer Guide) was not fetched in full.

## Q4. KV260 peripherals: PS-connected vs PL-connected; can a PL-only CPU use display, USB HID and SD?

### Takeaway
Every "PC-like" peripheral on the KV260 sits on the PS: USB 3.0 (4 ports via a hub), DisplayPort and HDMI (both from the PS DisplayPort controller over PS-GTR, split by an STDP4320), Gigabit Ethernet, microSD, QSPI and eMMC. The PL owns only the camera interfaces (2× IAS MIPI, RPi camera on HPA), the Pmod and the fan PWM pin. There is no PL-native HDMI TX. A PL-only RISC-V therefore has two options. It can drive the PS controllers as AXI register/DMA devices from the PL, which is possible in hardware but needs Linux drivers that today assume ZynqMP firmware services. Or it can bit-bang or add its own peripherals on Pmod or other PL pins, which is very limited.

### Cited Findings
- "The DP controller subsystem in the PS is coupled to the STDP4320 De-multiplexer on the carrier card, which consists of dual mode output ports configured as DP and HDMI." So the HDMI (J5) and DP (J6) outputs both come from the PS DisplayPort controller — [KV260 Smart Camera design overview](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/smartcamera/docs/introduction.html)
- PS-GTR transceivers (x4, up to 6.0 Gb/s) support "SGMII, tri-speed Ethernet, PCI Express Gen2, SATA, USB3.0, and DisplayPort". PS peripherals include 4 GEM, the DisplayPort controller with DMA, 2 USB 3.0/2.0 controllers, and SD/eMMC: "one ... controller can be used as a carrier card peripheral from MIO[22:13], the other eMMC controller is reserved for the eMMC on the SOM" — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf)
- The carrier card has 4 USB 3.0 ports (U44, U46), 5 V at up to 900 mA per port with 2.1 A total, plus an RJ45 1 Gb/s Ethernet port, microSD (J11, "boot device"), HDMI J5, DP J6, Pmod J2, IAS0 J7 (4-lane MIPI through an OnSemi AP1302 ISP), IAS1 J8 (4-lane MIPI), and an RPi camera J9 ("2 MIPI lanes connected directly to the Zynq UltraScale+ MPSoC HPA bank"). It also has an FTDI USB-UART/JTAG (J4) and a direct JTAG header (J3) — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Fan: "The fan gating signal is connected to a FPGA HD I/O bank pin". LiteX maps it to A12 (LVCMOS33) — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf), [litex-boards platform](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/platforms/xilinx_kv260.py). The Pmod pins are H12 E10 D10 C11 B10 E12 D11 B11 (3.3 V, HDIO) — [litex-boards platform](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/platforms/xilinx_kv260.py)
- Reset fabric (UG1089 Figure 4): SD_CARD_RESET_B, USB_PHY_RESET_B, USB_HUB_RESET_B, ETH_RESET_B, IAS_ISP_RESET_B, IAS_DIRECT_RESET_B and RPi_RESET_B are driven from a mix of PS_MIO and HDIO (PL) signals — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf). The extracted figure layout lists three PS_MIO and three HDIO drivers. The exact mapping of which reset goes on which (for example, whether USB_HUB_RESET_B is on HDIO) is ambiguous in the text extraction. **Verify against the KV260 carrier schematic or XDC.**
- The ZynqMP DisplayPort subsystem accepts "live" video from the PL as native video, as well as non-live frame buffers through its DPDMA. Bare-metal drivers (dppsu, avbuf, dpdma) exist in the Xilinx embedded SW repo. "DisplayPort live input in Linux OS is not supported" (at the time of that wiki text). A 2024 LKML patch series adds live-input format setting — [AMD wiki ZynqMP Standalone DP driver](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842318/ZynqMP+Standalone+DisplayPort+Driver), [LKML DPSUB live video patch](https://lkml.rescloud.iu.edu/2403.2/05585.html), [kernel docs](https://docs.kernel.org/gpu/zynqmp.html)
- A PL master can reach PS slaves (IOP peripherals in the LPD) through S_AXI_LPD, and the FPD/DDR through the HP/HPC ports — [UG1085 Table 2-13](https://0x04.net/~mwk/xidocs/ug/ug1085-zynq-ultrascale-trm.pdf)
- Users report USB ports dead on the KV260 until the right image or firmware is loaded, along with Ethernet "PHY reset timed out" boot errors. This is consistent with resets and clocks depending on firmware and PL configuration — [AMD forum, dead USB](https://adaptivesupport.amd.com/s/question/0D52E00006mGMZ6SAO/my-kria-kv260s-usb-ports-are-dead-neither-wireless-keyboard-mouse-thumb-drives-cameras-are-recognized-at-the-ports-there-are-no-dmesgs-indicated-any-errors-usbdevices-lsusb-lblk-v4l2ctl-commands-do-not-indicate-any-device-is-connected?language=en_US) (anecdotal)

### Inferences
- **Display:** A PL RISC-V can use the PS DP controller. It would program DP/AVBUF/DPDMA registers through an AXI master into the PS, or use the live-video path, with the PL generating pixels and timing while the RISC-V does one-time setup over AXI. DP link training is done by software, but that software can run on the RISC-V (port the standalone dppsu driver or the Linux zynqmp_dp driver). The PS-GTR lanes and DP reference clock must be configured by psu_init/FSBL. No ARM software is needed at runtime, in principle.
- **USB HID:** The PS USB controllers are Synopsys DWC3. Mainline Linux has a generic dwc3 driver, but the Xilinx glue (dwc3-xilinx) and its clocks and resets use the ZynqMP firmware interface (EEMI calls through TF-A/PMUFW SMCs). A riscv64 kernel cannot make those SMCs. The workaround is to have the FSBL/psu_init leave the USB clocks and resets enabled, then use a plain "snps,dwc3" node with fixed clocks. This is plausible but unverified. The alternative is a soft USB host (for example, a LiteX USB OHCI/ULPI core on Pmod), which is limited to low/full speed and needs a PHY. The KV260's USB connectors are wired to the PS PHY and hub, not the PL.
- **SD card:** Same pattern. The PS SDHCI (Arasan, "sdhci-of-arasan") is register-compatible with generic SDHCI. Clocks and tap delays are normally set through the ZynqMP firmware, so they would need static configuration in psu_init. The microSD slot is wired only to PS MIO, so a PL SD core (LiteSDCard) cannot reach it.
- **Interrupts:** PS peripheral interrupts are routed to the GIC. The PS→PL interrupt path (IRQ outputs to PL) exists for some peripherals, but routing every PS peripheral IRQ to a PL PLIC needs checking. Polling is the fallback. This is unverified.
- **Net:** "No ARM software" is feasible for display only with significant driver porting effort. USB and SD are feasible only if the RISC-V Linux drives Xilinx PS IP with ZynqMP-firmware dependencies removed. This is novel engineering with no prior art found.

### Gaps
- I did not find any project where a PL soft CPU running Linux drives the ZynqMP PS USB, DP or SDHCI controllers.
- I did not confirm the exact KV260 USB topology. I believe it is a USB5744 hub plus a ULPI USB3320 PHY on MIO, with USB3 on a PS-GTR lane, but the user guide text extraction did not show part numbers.
- I did not confirm the PS→PL IRQ availability for USB, SD and DP.

## Q5. Power draw, input voltage and cooling

### Takeaway
The KV260 needs a 12 V 3 A (36 W) adapter. The SOM is fed from 5 V (VCC_SOM) at a maximum of 4 A, which is 20 W absolute SOM ceiling. AMD sizes the fansink for a "full 10W ... application power budget". There is an always-on 12 V fan (PWM-able from a PL pin). I found no sourced measured idle or heavy-load wattage.

### Cited Findings
- "The AMD Kria KV260 Vision AI Starter Kit requires a 12V, 3A power supply adapter." The suggested adapter is CUI SMI36-12-V-P6, center-positive barrel jack J12. The carrier derives 5 V for the SOM — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- "The integrated fansink allows you to exercise the full 10W AMD Zynq UltraScale+ MPSoC application power budget without any additional accessories." The 12 V fan runs at constant speed by default, and "variable fan speed control can be implemented through a FPGA based PWM fan controller" — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- VCC_SOM is "5V (4.75V–5.25V)", with a maximum current of 4 A. A power monitor on VCC_SOM can be read over I2C (`xmutil platformstats`) — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7161/SM-K26-XCL2GI.pdf), [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- USB ports can source up to 2.1 A total at 5 V (about 10.5 W) — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)

### Inferences
- Laptop budget: about 10 W for the MPSoC under heavy PL load, plus carrier losses, fan (about 1 W), DDR and USB peripherals. That gives about 12–20 W at the 12 V input, which fits the 36 W adapter rating. The board needs 12 V, so a laptop battery pack needs a 12 V rail (a 3S Li-ion is 9–12.6 V, so it needs a buck-boost). These numbers are estimates.
- Parking the A53 cluster in reset or powering down the FPD's APU saves PS power. The DDRC and FPD switch must stay up.

### Gaps
- I found no reliable published measured idle or loaded watts for the KV260. The Hackster benchmarking article returned 403. Measure with `xmutil platformstats` or a USB-C/barrel power meter.
- Fan specs (CFM, dB) were not found.

## Q6. Existing soft RISC-V projects on K26/KV260 or other ZynqMP boards

### Takeaway
Soft RISC-V on the KV260 exists only as accelerator or co-processor experiments: VexRiscv attached to an ARM PetaLinux host, and LiteX targets that default to the A53 "zynqmp" CPU. On ZynqMP generally, Rocket-chip ports (fpga-zynq on ZCU102) ran RISC-V Linux with the ARM running PetaLinux as front-end server, sharing PS DDR through HP ports. I found no project that boots Linux on a PL soft CPU on a ZynqMP with the ARM cores idle.

### Cited Findings
- LiteX KV260 target: `cpu_type` defaults to "zynqmp" (A53 #0). The system clock comes from the PS clock when zynqmp is selected; otherwise an S7PLL from the platform default oscillator. DDR is reached through the PS (two 2 GB regions) — [litex-boards targets/xilinx_kv260.py](https://raw.githubusercontent.com/litex-hub/litex-boards/master/litex_boards/targets/xilinx_kv260.py)
- Japanese community projects ran VexRiscv in the KV260 PL with PetaLinux on the ARM, including PL→PS interrupts and a "RISC-V on KV260 platform for AI Edge contest" — [lp6m blog](https://lp6m.hatenablog.com/entry/2022/10/01/011526), [zenn sirokujira](https://zenn.dev/sirokujira/articles/kv260_setting_vexriscv), [zenn lightspeedesper](https://zenn.dev/lightspeedesper/scraps/22d7a784dc874f), [Qiita basaro_k](https://qiita.com/basaro_k/items/7001f006722b249a7404)
- Rocket chip on ZCU102: a port of fpga-zynq to ZCU102 (Vivado 2018.1, PetaLinux 2018.2), up to quad-core Rocket, about 180–195 MHz single-core, booting RISC-V Linux — [li3tuo4/rc-fpga-zcu](https://GitHub.com/li3tuo4/rc-fpga-zcu), [ncppd/rc-fpga-zcu](https://github.com/ncppd/rc-fpga-zcu), [riscv-boom/fpga-zynq](https://github.com/riscv-boom/fpga-zynq). In the fpga-zynq design the ARM runs Linux and a front-end server (fesvr) that loads and proxies the RISC-V. This is from my general knowledge of fpga-zynq and was not reconfirmed in this pass.
- vivado-risc-v (Rocket/BOOM, boots Debian riscv64 with OpenSBI/U-Boot) supports VC707, KC705, Genesys 2, Nexys Video, Nexys A7-100T and Arty A7-100T. The fetched README listed **no Zynq UltraScale+ or Kria support**. "DDR is provided by Vivado [MIG]. UART, SD and Ethernet are open source Verilog" — [eugene-tarassov/vivado-risc-v](https://github.com/eugene-tarassov/vivado-risc-v). The README may also list VCU118 or KCU105; the fetch summary did not show them, so check before citing.

### Inferences
- Ouroboros would be first-of-kind on the KV260 in two respects: ARM fully idle after FSBL, and PS USB/DP/SD driven from a RISC-V kernel. The closest reusable building blocks are LiteX (PS DDR access via the zynqmp HP port wrapper), vivado-risc-v (the Rocket+Linux boot stack on PL DDR boards) and the Xilinx standalone DP drivers.

### Gaps
- I found no CVA6 or NaxRiscv port to K26/KV260. I also found no Ubuntu riscv64 boot on any ZynqMP PL soft core.

## Q7. Alternative boards (if KV260 is too small) — LUTs and PL-attached DDR

### Takeaway
The KR260 uses the same K26 SOM, so the same 117k LUTs and PS-only DDR. The ZCU104 and ZCU106 (XCZU7EV, about 230k LUTs) add PL-side DDR4 (a SODIMM socket on the ZCU104, a 2 GB component on the ZCU106), but they still have PS-only USB, DP and SD. The Genesys 2 (Kintex-7 325T, about 204k LUTs, 1 GB PL DDR3) and VCU118 (VU9P, 1.18M LUTs, 2×4 GB PL DDR4) are pure FPGAs with no ARM at all. These are the cleanest fit for "no built-in CPU cores", and both are already supported by vivado-risc-v.

### Cited Findings
- KR260 Robotics Starter Kit is built on the same XCK26 K26 SOM — [LinuxGizmos](https://linuxgizmos.com/amd-robotics-starter-kit-based-on-zynq-ultrascale-xck26/)
- XCZU7EV: 504K system logic cells, about 230K CLB LUTs, 27 Mb UltraRAM — [search summary of vendor pages, e.g. Sundance/ALINX](https://www.sundancedsp.com/products/fpga-boards-modules/pcie-104/pcie104z-with-xilinx-zynq-us-mpsoc/)
- ZCU104: XCZU7EV PL banks 64/65/66 are wired to a DDR4 SODIMM socket (J1). The kit "is shipped without a DDR4 SODIMM installed". The recommended part is 4 GB x64 DDR4-2666 — [UG1267 ZCU104](https://www.mouser.com/pdfDocs/ug1267-zcu104-eval-bd.pdf), [manualslib page](https://www.manualslib.com/manual/1475689/Xilinx-Zcu104.html?page=29)
- ZCU106: "2 GB 64-bit wide DDR4 memory system comprised of four 256 Mb x 16 SDRAMs (Micron MT40A256M16GE-075E)" connected to PL banks 64/65/66, in addition to its PS DDR4 — [UG1244 ZCU106](https://www.mouser.com/datasheet/2/903/ug1244-zcu106-eval-bd-1596082.pdf)
- Genesys 2: XC7K325T-2FFG900C, 50,950 slices (4 LUTs each, so about 203,800 LUTs), 840 DSP, about 16 Mb BRAM, "1GB 1800Mbps on-board DDR3" on the PL — [Digilent Genesys 2 reference](https://digilent.com/reference/programmable-logic/genesys-2/start)
- VCU118: XCVU9P, 1,182,240 CLB LUTs, 6,840 DSP48E2, 75.9 Mb BRAM, 2× DDR4 component interfaces (80-bit each, 2× 4 GB) — [UG1224 VCU118](https://www.mouser.com/datasheet/2/903/ug1224-vcu118-eval-bd-1596504.pdf); figures via [PCBSync](https://pcbsync.com/xilinx-vcu118/) search summary

### Inferences
- If "no built-in CPU cores" is a hard requirement, a non-SoC FPGA board removes the whole FSBL/PS dependency. Every peripheral, PL DDR, USB (via PL PHY or an MCU-based HID bridge), HDMI and SD would then be driven by soft IP. The Genesys 2 has HDMI in/out, a USB-HID host bridge MCU (PIC24) and microSD all on the PL. That is from general knowledge; verify on the Digilent page. It is a cheap, proven Linux target (vivado-risc-v) at about 204k LUTs, but it has only 840 DSP and 1 GB DDR3 at about 7.2 GB/s theoretical (32-bit × 1800 MT/s, my arithmetic).
- ZCU104/106 remain ZynqMP. They still need an ARM FSBL to configure the PL from flash, unless the PL is configured over JTAG. Their PL DDR4 does let the soft CPU own a private MIG memory.
- The VCU118 is about 6× the KV260 but is a large, high-power (tens of W) board that is unsuitable for a laptop.

### Gaps
- I did not verify current 2026 pricing or availability for any board.
- I did not verify the ZCU104 PS DDR size (believed 2 GB component) or the ZCU106 PS DDR (believed a 4 GB SODIMM).
- Power figures for the alternative boards were not gathered.
