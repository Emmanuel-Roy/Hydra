# Physical hardware for a KV260 / K26-based laptop (Ouroboros)

Research date: 2026-09-30. Prices are in USD unless noted and are those shown by the cited pages or search snippets around Sept 2026. Search-snippet prices fluctuate, so treat them as approximate. Anything marked **[GUESS]** or **[INFERENCE]** has no direct source.

## 1. KV260 power, thermals and K26 SOM power rails

### Takeaway
The KV260 runs from a single **12 V, 3 A (36 W) barrel jack** (2.5 mm ID / 5.5 mm OD, centre positive). The carrier makes 5 V for the SOM (VCC_SOM, 4.75–5.25 V, up to 4 A). AMD sizes the fansink for a "10 W MPSoC application power budget." Typical whole-kit draw is probably about 5–15 W. I found no clean primary measurement of idle versus heavy-PL load. A custom carrier only has to supply 5 V, the VCCO rails for the PL banks and an RTC battery.

### Cited Findings
- The KV260 needs a 12 V, 3 A adapter. AMD suggests the CUI SMI36-12-V-P6, "+12V, 3A DC adapter using a center-pin positive barrel connector (2.5 mm ID, 5.5 mm OD)", which plugs into DC jack J12. No PSU comes in the box. — [UG1089 v1.3 (May 2024), mirror](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- The carrier's on-board regulator makes a 5 V supply. VCC_SOM is powered from that 5 V. The carrier turns on the PL VCCO rails after the SOM asserts VCCOEN_S_M2C / VCCOEN_PL_M2C. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Power telemetry: a power monitor on VCC_SOM can be read over I2C with AMD utilities. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Peripheral power budget: 4× USB 3.0 ports at up to 900 mA each, with a total of 2.1 A across all four. The Pmod supply pin is 3.3 V at 100 mA. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Fan and thermals: "The integrated fansink allows you to exercise the full 10W AMD Zynq UltraScale+ MPSoC application power budget." The fan is 12 V (connector J13) and runs at constant speed by default. "Variable fan speed control can be implemented through a FPGA based PWM fan controller. The fan gating signal is connected to a FPGA HD I/O bank pin." So the fan PWM lives in the PL, which the Ouroboros bitstream must provide or tie off. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- KV260 kit dimensions are 119 × 140 × 36 mm (carrier, SOM and fansink). — [AMD KV260 product brief](https://www.amd.com/content/dam/amd/en/documents/products/som/kria/k26/kv260-product-brief.pdf) (via search snippet)
- "Typical power 7.5 W, max 15 W". About 5 W during Vitis-AI inference at 25 FPS. — [emergentmind aggregator page](https://www.emergentmind.com/topics/amd-kria-kv260-system-on-module-som) (secondary source, not verified against AMD)
- One example of `xmutil platformstats -p` output shows "SOM total power: 3560 mW". The workload context is unclear, and this is the SOM rail only, not the whole carrier. — [element14 "XMUTIL … understanding platformstats"](https://community.element14.com/members-area/personalblogs/b/blog/posts/xmutil-understanding-platformstats) (search snippet; the page timed out on fetch)
- K26 SOM power rails (DS987 Table 16):
  - VCC_SOM: 5 V (4.75–5.25 V), 50 mV p-p maximum noise, **4 A maximum**.
  - VCC_BATT: 1.5 V for the RTC.
  - VCCO_HPA/HPB/HPC: 1.0–1.8 V at 1.0 A each.
  - VCCO_HDA/HDB/HDC: 1.2–3.3 V at 1.0 A each.
  - VCCO tolerance at the connector must be +3% / −2%.
  - Sequencing: VCC_SOM good → carrier releases PWROFF_C2M_L → SOM sequences itself → SOM asserts VCCOEN_PS_M2C / VCCOEN_PL_M2C → carrier enables the I/O rails.

  — [DS987 K26 SOM data sheet (DigiKey copy)](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)
- PWROFF_C2M_L does a hard power-down without telling software. For a graceful shutdown, use MIO31_SHUTDOWN plus the PMU. This matters for a laptop lid or power button and for battery-low cutoff. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)
- SOM temperature limits (MPSoC junction): K26C 0–85 °C, K26I −40–100 °C. The SOM has an aluminium heat spreader, and the system cooler must attach to it. Mechanical: 77 × 60 × 10.9 mm, 58 g. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)
- AirJet (Frore) solid-state cooler has been shown on a KV260. Frore claims it frees space for battery and enables thinner devices. — [Frore Systems KV260 page](https://www.froresystems.com/application/amd-kria-kv260) (vendor marketing)

### Inferences
- **[INFERENCE]** The 36 W PSU rating covers the board plus about 10 W of USB peripheral budget (2.1 A × 5 V). The SOM itself is capped at 20 W by the 4 A × 5 V rail. For battery sizing, a design point of **8–15 W** for board plus PL soft CPU, and about **15–25 W** with the display and keyboard, looks reasonable. A soft RISC-V at about 100–300 MHz will likely use only a small part of the 256 k logic cells, so PL dynamic power should be modest, but this needs measuring.
- **[INFERENCE]** In an enclosure, the 10 W fansink is enough for a soft-CPU design. Keep the stock fansink and duct air through vents. The PL must drive the fan-enable HDIO pin, or the fan should be left at its default full speed.
- To measure on real hardware, use `xmutil platformstats -p` for the SOM rail, plus a USB-C or barrel inline power meter for the whole board.

### Gaps
- There is no authoritative measured idle-vs-loaded whole-board figure. The Hackster benchmark article (Whitney Knitter) returned 403. UG1090 (K26 thermal design guide) was not retrieved.
- I could not confirm the KV260's allowed input range around 12 V, for example whether a 3S Li-ion pack's 9–12.6 V swing is OK. The carrier schematic or regulator datasheet is needed for this.

## 2. Battery and power path

### Takeaway
The simplest path is an off-the-shelf **12 V Li-ion pack with DC output**, about 66 Wh, for about $30–45. A sturdier path is a **USB-C PD power bank plus a 12 V PD-trigger board** (a few dollars). For "charge while running" and safety, a custom carrier can copy MNT Reform's approach: a multi-chemistry buck-boost charger (TI BQ25756) with a 4S LiFePO4 or Li-ion pack. Expect very roughly 3–5 h at 10–20 W from a 60–70 Wh pack.

### Cited Findings
- TalentCell 12 V pack, "11.1V 6000mAh" (about 67 Wh nominal) with DC output and a 12.6 V 1 A charger: about $29.99 on Amazon, $30–58 elsewhere (2026 snippet). — [Amazon listing](https://us.amazon.com/Talentcell-Rechargeable-6000mAh-Battery-Portable/dp/B00MF70BPU); [SteadyGarage $39.99](https://www.steadygarage.com/products/talentcell-rechargeable-12v-lithium-ion-battery-pack-6000mah-usb)
- USB-C PD trigger ("decoy") boards fix the output at 5/9/12/15/20 V from a PD charger or power bank, up to 100 W. They are sold in multi-packs on Amazon and AliExpress. — [Amazon PD trigger 5/9/12/20 V 100 W](https://www.amazon.com/Trigger-Supports-5V9V12V20V-Suitable-Testing/dp/B0GSYPRMVZ); [Amazon 12 V-fixed 10-pack](https://www.amazon.com/Trigger-Module-Charge-Output-Delivery/dp/B0GWMWFXCG)
- MNT Reform Next: 8× LiFePO4 cells (16,000 mAh) on a TI BQ25756 multi-chemistry buck/boost charge controller that supports 4S2P LiFePO4 or 4S2P Li-ion. — [Crowd Supply MNT Reform Next](https://www.crowdsupply.com/mnt/mnt-reform-next) (via search snippet)
- MNT Pocket Reform: 2× 3.7 V 4000 mAh LiPo cells (EREMIT 606090, 6 × 60 × 90 mm, JST-PH), USB-C PD charging, about 4 h runtime. — [MNT Pocket Reform handbook, hardware](https://mntre.com/documentation/pocket-reform-handbook/hardware.html); [Crowd Supply](https://www.crowdsupply.com/mnt/pocket-reform)
- CrowView Note laptop shell: 7.4 V 5000 mAh (about 37 Wh) battery, charged from a 12 V/4 A DC jack. It can power an SBC at 5 V/3 A (USB-C) or 5 V/5 A (USB-C power port), but only at **5 V, not 12 V**. — [CNX Software review](https://www.cnx-software.com/2024/08/17/crowview-note-review-a-14-inch-laptop-shell-designed-for-raspberry-pi-5-and-jetson-nano-developer-kit/)
- The Antmicro open K26 carrier takes power from PoE, USB-C PD or a DC jack. This is a precedent for PD-powered K26 carriers. — [antmicro/kria-k26-devboard](https://github.com/antmicro/kria-k26-devboard)
- Raspberry Pi laptop builds commonly use 18650 cells with a UPS HAT, for example 2× 5000 mAh cells or 4× 18650 for about 3 h on a Pi 5. — [Hackster: Portable Pi 84](https://www.hackster.io/news/portable-pi-84-is-a-unique-diy-laptop-you-can-3d-print-today-af3abe0e265c); [CircuitDigest Pi 5 laptop](https://circuitdigest.com/news/sleek-10-inch-3d-printed-raspberry-pi-5-laptop-with-touchscreen)

### Inferences
- **[INFERENCE] Runtime arithmetic:** a 67 Wh pack × about 0.85 converter efficiency ≈ 57 Wh usable, which gives about 5.7 h at 10 W, 3.8 h at 15 W and 2.8 h at 20 W. A 37 Wh pack (CrowView-class) gives about 1.5–3 h. The CNX review measured about 40 min under full CPU stress and about 1.5 h in typical use for a Pi 5 plus the screen.
- **[INFERENCE] Charge-while-running:** the TalentCell-style packs and USB-C PD power banks generally allow pass-through charging, but some cut the output briefly when the charger is connected or removed. That would reset the KV260, so it needs testing. A real power-path charger (BQ25756/BQ25713-class) on a custom carrier avoids this.
- **[INFERENCE] Safety:**
  - Use packs with a built-in BMS covering over-current, over- and under-voltage, and short circuit.
  - Fuse the 12 V line.
  - Avoid bare cells inside a 3D-printed enclosure without a protection board.
  - LiFePO4 (as MNT uses) trades energy density for thermal safety.
  - Packs under 100 Wh are normally carry-on-acceptable for air travel. **[GUESS]** I did not look up the regulation text.

### Gaps
- I did not verify the TalentCell's exact output range (about 12.6 V full to about 9–10 V cut-off) against the KV260 input regulator's minimum.
- There is no source on whether the KV260 tolerates the output glitch during pass-through charging.

## 3. Display

### Takeaway
On the KV260, **both HDMI and DisplayPort come from the PS DisplayPort controller** (DP 1.2a), and the HDMI 1.4 port is fed through an STDP4320 splitter. **No video output is PL-driven.** A soft RISC-V in the PL can still reach the screen in two ways:
- It writes a framebuffer into DDR (through S_AXI_HP) that the PS DP DMA scans out, which needs some PS-side setup.
- It feeds the DP controller's **"live video" input from the PL**. This is supported in bare-metal drivers and only partly in Linux.

Either way, any HDMI monitor, portable monitor, laptop shell or eDP panel on an HDMI-to-eDP board works on the output side.

### Cited Findings
- Block diagram and connectors: DisplayPort 1.2a (J6) and HDMI 1.4 (J5) both hang off a "Video Splitter". — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- "The DP controller subsystem in the PS is coupled to a STDP4320 de-multiplexer on the carrier card… dual mode output ports configured as DP and HDMI." Both ports carry the same image. HDMI on KV260 "is coming from the PS". — [Kria apps docs, NLP-SmartVision design overview](https://xilinx.github.io/kria-apps-docs/kv260/2022.1/build/html/docs/nlp-smartvision/docs/introduction_nlp.html); [AMD forum "Kria KV260 HDMI"](https://adaptivesupport.amd.com/s/question/0D54U00006rWnoBSAS/kria-kv260-hdmi?language=en_US) (via search snippets)
- ZynqMP DP subsystem:
  - It supports in-memory framebuffers via DPDMA and "live" video and audio from the PL.
  - Link rates are RBR 1.62, HBR 2.7 and HBR2 5.4 Gb/s, on 1, 2 or 4 lanes in the driver API.
  - Video and audio clocks can be sourced from the PS or the PL.
  - "Not all features are currently supported."

  — [Linux kernel doc: ZynqMP DisplayPort subsystem](https://docs.kernel.org/gpu/zynqmp.html)
- The DP subsystem has a 36-bit native video input from the PL. Live input is described as experimental in some AMD material, and older wiki text says PS DP live input is not supported in Linux. Standalone (bare-metal) drivers use `avbuf` to enable the PL path. — [Xilinx wiki ZynqMP Standalone DP driver](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842318/ZynqMP+Standalone+DisplayPort+Driver); [UG1449 DisplayPort interface](https://docs.amd.com/r/en-US/ug1449-multimedia/DisplayPort-Interface); an [AMD forum thread on live input with TPG](https://adaptivesupport.amd.com/s/question/0D5Pd00000nCZ17KAG/zynqmp-displayport-live-video-input-with-tpg-under-linux-no-output-tpg-driver-not-probed?language=en_US) shows users hitting issues (search snippets)
- Pixel clocks:

  | Mode | Pixel clock | Source |
  |---|---|---|
  | 1024×768 @ 60 | 65.000 MHz | VESA DMT |
  | 1280×720 @ 60 | 74.25 MHz | VESA DMT / CEA |
  | 1920×1080 @ 60 | 148.5 MHz | Standard CEA-861 timing; not seen in the fetched snippet |

  — [VESA DMT 1.13](https://glenwing.github.io/docs/VESA-DMT-1.13.pdf); [tinyvga timing](http://www.tinyvga.com/vga-timing)
- Laptop eDP panel driver boards (HDMI to eDP, for 30- or 40-pin panels such as the 14" 1920×1080 NV140FHM family) cost about $17–22 on eBay. The boards measure about 82 × 60 × 5 mm. Panels must match the board's firmware and part number. — [eBay NV140FHM-N41 kit $20.98](https://www.ebay.com/itm/167229239433); [eBay NV140FHM-N4C/N4F $18.70](https://www.ebay.com/itm/165624012939)
- Waveshare 13.3" 1920×1080 IPS HDMI/USB-C touch monitors cost $144.99–159.99 from Waveshare, or €175 / $209.95 at retailers. — [Waveshare 13.3" FHD monitor](https://www.waveshare.com/13.3inch-fhd-monitor.htm); [Waveshare 13.3" HDMI LCD (H)](https://www.waveshare.com/13.3inch-hdmi-lcd-h.htm); [PiShop $209.95](https://www.pishop.us/product/13-3inch-hdmi-lcd-h-display-with-case-1920x1080-ips/)
- Laptop shells, which combine screen, keyboard, touchpad and battery and have no computer inside:
  - **CrowView Note** (Elecrow): 14" 1920×1080 60 Hz IPS, mini-HDMI in, USB-C with DP, USB-A ports for keyboard and touchpad, 334 × 223 × 20 mm, 1.2 kg. Priced from $129.9 (CNX, 2024) or $169 (other review).
  - **NexDock 6**: $229 (Dec 2025).
  - **NexDock XL** (15.6"): $349, mini-HDMI 1.4a in.

  — [CNX CrowView review](https://www.cnx-software.com/2024/08/17/crowview-note-review-a-14-inch-laptop-shell-designed-for-raspberry-pi-5-and-jetson-nano-developer-kit/); [Elecrow/CrowPi product page](https://www.crowpi.cc/products/crowview-note-all-in-one-portable-monitor-phone-to-laptop-device-with-full-featured-type-c-sbcs-mini-pc-pc-game-console-compatibility); [BigGo NexDock 6](https://biggo.com/news/202512171324_NexDock-6-Lapdock-Launch-Phone-to-Laptop)

### Inferences
- **[INFERENCE]** The cleanest Ouroboros route: the soft RISC-V (or its display controller in the PL) writes a framebuffer to DDR, and a small one-time PS setup (FSBL or PMU, or an R5/A53 stub) configures DPDMA and the DP link. Alternatively, the PL generates timing and pixels into the DP live-video input with a PL-sourced pixel clock. Then the KV260's own HDMI or DP port drives an off-the-shelf panel. 1280×720 or 1024×768 (65–74.25 MHz) is easy for PL timing logic. 1920×1080 at 148.5 MHz is also routine for UltraScale+ fabric. The real limit is the DDR bandwidth the soft CPU's framebuffer consumes: 1080p60 at 32 bpp is about 0.5 GB/s, small compared with the PS DDR4.
- **[INFERENCE]** A PL-only video path on the KV260 is limited to the single Pmod (8 signals at 3.3 V). That allows a crude 2-2-2-bit VGA (64 colours) or an SPI or parallel small LCD. It works as a fallback debug display but not as a laptop screen.
- **[INFERENCE]** A native-eDP laptop panel is only possible on a custom carrier, by routing PS-GTR lanes as eDP, or using PL GTH with a DP TX IP (licensed) or an open core. On a KV260, use an HDMI-to-eDP board.

### Gaps
- I did not confirm whether the STDP4320's HDMI output accepts every DP timing, for example odd panel resolutions.
- I did not confirm the exact DPDMA/live-mode status in the 2025.x Linux or bare-metal releases.

## 4. Input devices

### Takeaway
On a stock KV260, all USB ports go through the **PS USB controller**, a ULPI PHY and a USB 3.0 hub on PS MIO. Neither the PL nor a soft CPU can reach them directly at the pin level. There are three practical options:
1. A PS-side helper (R5/A53) bridges HID events to the soft CPU.
2. A **Pmod PS/2** ($9–10) plus a PS/2 keyboard.
3. A tiny **PL USB HID host core** on Pmod pins (under 300 LUTs), driving a USB low-speed or full-speed keyboard or touchpad directly.

Ready-made laptop keyboards include MNT's standalone USB keyboards and laptop shells that expose the keyboard and touchpad as USB HID.

### Cited Findings
- The KV260 has 4× USB 3.0 ports via a USB hub on the PS. Reset nets USB_PHY_RESET_B and USB_HUB_RESET_B are on PS_MIO. — [UG1089 (block diagram and Figure 4 reset tree)](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Zynq UltraScale+ has two USB 3.0/2.0 controllers, xHCI-compliant, with a 64-bit AXI master DMA. Twelve AXI ports link PS and PL, including S_AXI_LPD, S_AXI_HP(C) and S_AXI_ACE/ACP. A cached PL master (MicroBlaze) can be coherent with A53 caches through ACE. — [UG1085 TRM (copy)](https://users.ece.utexas.edu/~mcdermot/arch/articles/Zynq/ug1085-zynq-ultrascale-trm%20copy.pdf); [Xilinx wiki cache coherency](https://xilinx-wiki.atlassian.net/wiki/spaces/A/pages/18842098/Zynq+UltraScale+MPSoC+Cache+Coherency) (search snippets)
- Pmod connector J2 is a Digilent 2×6 header at 3.3 V on PL HDIO. The reset tree shows the PL side on HDIO at 3.3 V. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- Digilent Pmod PS2 (410-094): $10.00 from Digilent, $8.99 at Mouser, DigiKey and Jameco. — [Digilent shop](https://digilent.com/shop/pmod-ps2-keyboard-mouse-connector/); [DigiKey](https://www.digikey.com/en/products/detail/digilent-inc/410-094/4090142)
- nand2mario `usb_hid_host`: a compact FPGA USB HID host for keyboards, mice and gamepads. It supports low speed (1.5 Mb/s) and full speed (12 Mb/s) from a single 12 or 60 MHz clock and uses fewer than 300 LUTs, fewer than 250 registers and 1 BRAM. — [GitHub nand2mario/usb_hid_host](https://github.com/nand2mario/usb_hid_host)
- OpenCores `usbhostslave`: a USB 1.1 host and function core (Verilog) supporting full and low speed, and control, bulk, interrupt and isochronous transfers. — [OpenCores usbhostslave](https://opencores.org/projects/usbhostslave)
- A minimal FPGA USB-HID host connects low-speed devices' D+/D− directly to two FPGA GPIOs through 27 Ω series resistors and 3.6 V Zener clamps. — [GitHub Circuit-killer/fpga-usbhid-host](https://github.com/Circuit-killer/fpga-usbhid-host)
- BoxLambda (a soft-SoC project) documents USB HID keyboard and mouse handling, including keyboard LEDs, in an FPGA SoC. — [BoxLambda USB HID](https://epsilon537.github.io/boxlambda/usb-hid/)
- MNT standalone USB keyboards and modules:
  - MNT Pocket Reform standalone keyboard with 15 mm optical trackball: €139.
  - MNT Reform Keyboard 4.0: €190–220.
  - Reform optical trackball module: €50.
  - Reform capacitive trackpad module: €50 (out of stock at time of search).
  - Reform keyboards use an RP2040 to scan the matrix and report USB HID.

  — [MNT shop: Pocket Reform keyboard](https://shop.mntre.com/products/mnt-pocket-reform-standalone-keyboard); [MNT shop: Reform USB keyboard](https://shop.mntre.com/products/mnt-reform-usb-keyboard-standalone); [MNT trackball](https://shop.mntre.com/products/mnt-reform-optical-trackball-module); [MNT trackpad](https://shop.mntre.com/products/mnt-reform-capacitive-trackpad-module); [Crowd Supply Reform Next](https://www.crowdsupply.com/mnt/mnt-reform-next)
- Penkesu uses an open-hardware Koda keyboard running QMK in a 3D-printed case. — [Raspberry Pi magazine / search summary](https://magazine.raspberrypi.com/articles/build-laptop-raspberry-pi)

### Inferences
- **[INFERENCE]** PL masters can probably program the PS USB xHCI registers through S_AXI_LPD, since the USB controllers sit in the LPD/IOU address map. In principle, a soft CPU with an xHCI driver could therefore use the KV260's USB ports. That means writing a full xHCI stack plus hub support (USB5744-class hub on the carrier). I could not verify this from a primary source. It is far heavier than a PL HID core on the Pmod.
- **[INFERENCE]** The recommended order of options:
  1. PL USB HID host core on 2 Pmod pins plus a USB-A breakout, so any low- or full-speed USB keyboard works. Many keyboards and touchpads enumerate at full speed, and composite devices or internal hubs complicate things.
  2. Pmod PS2 plus a PS/2 keyboard, or a USB keyboard that still supports PS/2 mode.
  3. A UART bridge: an RP2040 or Pico running a USB host (PIO-USB) converts HID to serial into the PL. This is robust and costs about $5. **[GUESS]** on price.
  4. A laptop shell's USB-HID keyboard and touchpad plugged into option 1 or 3.
- The single KV260 Pmod (8 I/O) must be shared between keyboard, SD and debug. This is a real constraint. Pmod pins: 2 for USB-HID, 4 for SPI-SD, 2 for spare or UART.

### Gaps
- There is no primary confirmation of PL-master access to PS USB registers, nor of anyone driving ZynqMP xHCI from a soft CPU.

## 5. Storage

### Takeaway
On the KV260, the **microSD (J11) is wired to the PS SD controller on MIO**. It is also the secondary boot device, and the production SOM's 16 GB eMMC is also on PS MIO. The PL can reach storage only through the Pmod, for example a **Digilent Pmod MicroSD ($8) in SPI mode**, or through a PS bridge. There is no NVMe on the KV260.

### Cited Findings
- Boot: primary QSPI on the SOM, secondary SD card on the carrier (SD_CARD_RESET_B on PS_MIO). U-Boot hands off to the SD card. SDHC cards are recommended. Production SOMs include both QSPI and eMMC. — [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf)
- K26 SOM: 16 GB eMMC on MIO500 via the PS SD controller, 64 MB QSPI, 4 GB DDR4. There is one SD/SDIO 2.0/eMMC 4.51 controller. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf); [DigiKey SM-K26 listing](https://www.digikey.com/en/products/detail/amd/SM-K26-XCL2GC/13985266)
- Digilent Pmod MicroSD (410-380): $8.00 from Digilent, about $7.86 at DigiKey. — [Digilent](https://digilent.com/shop/pmod-microsd-microsd-card-slot/); [DigiKey](https://www.digikey.com/en/product-highlight/d/digilent/microsd-card-slot)
- PS-GTR (4 lanes, 6 Gb/s) supports PCIe Gen2, SATA, USB 3.0, DP and SGMII. On a custom carrier these could host M.2 SATA or NVMe (PCIe Gen2 x1–x4), but the KV260 already uses them for USB and DP. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)

### Inferences
- **[INFERENCE]** SPI-mode SD from the PL gives roughly 1–3 MB/s at 25 MHz SPI, which is enough for a soft-CPU OS. A 4-bit SD-native PL controller on the Pmod would need 6 pins (CLK, CMD, D0–3) and leave only 2 for input.
- **[INFERENCE]** An alternative is to put the soft CPU's disk image in DDR (RAM-disk) or in a partition on the eMMC or SD, with PS firmware acting as a block-device server over shared memory. This avoids the Pmod entirely.

### Gaps
- I did not verify whether the PS SD controller registers can be driven directly from a PL master, which has the same open question as USB.

## 6. Prior art: DIY FPGA and SBC laptops, enclosures and licences

### Takeaway
Fully open laptops (MNT Reform and Pocket Reform, Novena, Olimex TERES-I) and FPGA-soft-CPU handhelds (bunnie's Precursor running VexRiscv on a Spartan-7) are good templates. I found no published KV260/Kria laptop or handheld build. Laptop shells (CrowView, NexDock) and 3D-printed Pi laptops show the low-effort route.

### Cited Findings
- **MNT Reform Next**:
  - RP2040 keyboard, 4S2P LiFePO4 or Li-ion pack with BQ25756.
  - KiCad sources under **CERN-OHL-S 2.0**.
  - Crowdfunded from $1,099.

  **MNT Pocket Reform**: €850–1,400; €1,099 for the ready-to-use model.

  — [Crowd Supply Reform Next](https://www.crowdsupply.com/mnt/mnt-reform-next); [Liliputing](https://liliputing.com/mnt-reform-next-crowdfunding-campaign-is-live-open-source-laptop-for-1099-and-up/); [MNT shop Pocket Reform](https://shop.mntre.com/products/mnt-pocket-reform); [MNT Reform handbook hardware](https://mntre.com/documentation/reform-handbook/hardware.html)
- **Precursor (bunnie)**:
  - XC7S50 Spartan-7 running VexRiscv RV32IMAC + MMU at 100 MHz, plus an iCE40UP5K embedded controller.
  - 16 MB SRAM, 128 MB flash.
  - 336×536 monochrome LCD, physical keyboard, 1100 mAh Li-ion battery.
  - 138 × 69 × 7.2 mm, 96 g.

  This is the closest prior art to a "soft RISC-V on FPGA portable". — [bunnie's blog](https://www.bunniestudios.com/blog/2020/introducing-precursor/); [Electronics-Lab](https://www.electronics-lab.com/precursor-open-hardware-risc-v-system-on-chip-soc-mobile-development-kit/)
- **Novena** (bunnie and xobs): an open laptop with an FPGA on the motherboard. — [Hackaday: Building the Novena laptop](https://hackaday.com/2016/01/30/building-the-novena-laptop/)
- **Olimex TERES-I**: an open DIY laptop kit (Allwinner A64) with expansion connectors intended for an FPGA add-on. — [GitHub OLIMEX/DIY-LAPTOP](https://github.com/OLIMEX/DIY-LAPTOP)
- **Portable Pi 84**:
  - FreeCAD 3D-printed enclosure with heat-set inserts.
  - Ortholinear mechanical keyboard.
  - 9.3" 1600×600 Waveshare display.
  - 2× 18650 cells via a UPS HAT.

  — [Hackster](https://www.hackster.io/news/portable-pi-84-is-a-unique-diy-laptop-you-can-3d-print-today-af3abe0e265c)
- **Pi 5 3D-printed 10.1" laptop**: Geekworm UPS with 4× 18650 cells, about 3 h. — [CircuitDigest](https://circuitdigest.com/news/sleek-10-inch-3d-printed-raspberry-pi-5-laptop-with-touchscreen)
- **Antmicro K26 devboard**: an open (Apache-2.0) KiCad 7 K26 carrier. — [GitHub](https://github.com/antmicro/kria-k26-devboard); [Antmicro blog](https://antmicro.com/blog/2022/09/kria-ultrascale-plus-som-baseboard)
- Search for Kria-specific portables found only Frore AirJet marketing about KV260 handheld and mini-PC cooling, not a real build. — [Frore](https://www.froresystems.com/application/amd-kria-kv260)
- CERN-OHL has three variants (P = permissive, W = weakly reciprocal, S = strongly reciprocal). — [Wikipedia CERN OHL](https://en.wikipedia.org/wiki/CERN_Open_Hardware_Licence)

### Inferences
- **[INFERENCE]** For Ouroboros, a reasonable licence choice is CERN-OHL-S (as MNT uses) or CERN-OHL-W for the carrier and enclosure, and Apache-2.0 if reusing Antmicro's carrier as a base. Apache-2.0 is compatible as an upstream for a CERN-OHL-S derivative, but **[GUESS]** a licence check is needed.
- **[INFERENCE]** 3D-printed clamshell approach: a bottom tray holds the KV260 (119 × 140 mm, 36 mm tall with fansink) and battery. The lid holds a 13–14" panel and driver board. The 36 mm board height makes the base thick (≥ 45 mm), so a custom low-profile carrier or a flat heatsink would be needed for anything slim.

### Gaps
- I found no published KV260/K26 laptop or handheld. Coverage of Hackaday.io "FPGA laptop" projects was shallow.

## 7. Custom K26 carrier board for a laptop

### Takeaway
The K26 connects through **two Samtec AcceleRate HD 0.635 mm 4-row 240-pin connectors** (SOM240_1 and SOM240_2; carrier part ADM6-60-01.5-L-4-2-A, about $19–28 each). The SOM needs only a 5 V / 4 A rail plus VCCO rails, which makes a laptop carrier quite feasible. Antmicro's open 8-layer, non-HDI carrier (118 × 100 mm) shows the complexity class.

A laptop carrier could integrate:
- a USB-C PD sink and battery charger (BQ25756-class),
- eDP from PS-GTR (DP controller),
- a USB hub on the PS USB,
- a keyboard-matrix microcontroller (RP2040) or the matrix directly on PL HDIO,
- PL-reachable SD/USB-HID,
- M.2.

### Cited Findings
- Connectors: "Samtec 0.635 mm AcceleRate HD high-density 4-row, 60 position connector set". The carrier terminal is ADM6-60-01.5-L-4-2-A. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf); [UG1091 (mikrocontroller.net mirror; 403 on fetch, snippet only)](https://www.mikrocontroller.net/attachment/573192/ug1091-carrier-card-design.pdf)
- SOM240_1 carries MIO501/502 (PS peripherals: USB, SD, UART, etc.), HPIO bank 66 (HPA), HDIO bank 45 (HDA), the 4 PS-GTR lanes and sideband and power signals. SOM240_2 carries the remaining HPIO and HDIO banks and the 4 GTH lanes. VCC_SOM pins are on both connectors. — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)
- PL I/O on the SOM connectors:
  - HDIO: 69 pins at 1.2–3.3 V (HDA 21, HDB 24, HDC 24).
  - HPIO: 58 differential pairs at 1.0–1.8 V (HPA 16 pairs, HPB 21, HPC 21).
  - GTH: 4 × 12.5 Gb/s.
  - PS-GTR: 4 × 6 Gb/s.
  - PS: DP controller, 2× USB 3.0/2.0, SD/SDIO, GbE, etc.

  — [DS987](https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/7171/122_SM-K26-XCL2GC.pdf)
- Antmicro open carrier:
  - KiCad 7, Apache-2.0, 118 × 100 mm ("30% smaller" than AMD's kit).
  - "Affordable 8 layer board without using costly HDI technology".
  - Power from PoE, USB-C PD or DC jack.
  - DP out, 4× USB 3.2 Gen1, GbE, M.2 key E, 2× 4-lane MIPI CSI-2, Pmod, microSD UHS-I.

  — [Antmicro blog](https://antmicro.com/blog/2022/09/kria-ultrascale-plus-som-baseboard); [GitHub](https://github.com/antmicro/kria-k26-devboard)
- AMD's custom carrier card software flow is documented. — [Kria custom CC flow](https://xilinx.github.io/kria-apps-docs/creating_applications/2022.1/build/html/docs/custom_cc_flow.html)
- Samtec ADM6-60-01.5-L-4-2-A(-TR) pricing: $25.94 for 1 at OnlineComponents, $23.08 for 1 at LCSC, $27.73 for 1 at Newark. One aggregator snippet called the -TR variant "obsolete", which I could not confirm. Check the Samtec lifecycle before committing. — [OnlineComponents](https://www.onlinecomponents.com/en/productdetail/samtec/adm660015l42atr-54696303.html); [LCSC](https://www.lcsc.com/product-detail/C3649973.html); [Newark](https://www.newark.com/samtec/adm6-60-01-5-l-4-2-a-tr/0-635-mm-accelerate-hd-high-density/dp/94AH6116)
- K26 SOM (commercial, SM-K26-XCL2GC): MSRP $325, $406.25 at DigiKey, $377 at Avnet, $422.46 at Mouser and Newark. — [DigiKey](https://www.digikey.com/en/products/detail/amd/SM-K26-XCL2GC/13985266); [AMD K26C page](https://www.amd.com/en/products/system-on-modules/kria/k26/k26c-commercial.html)
- JLCPCB 8-layer PCBs start at about $82 for 5 pieces (small sizes), with free impedance control and via-in-pad. — [JLCPCB impedance](https://jlcpcb.com/impedance); [King Sun 8-layer price guide (third party)](https://www.kingsunpcb.com/8-layer-pcb-price-guide-2025/) (search snippets)

### Inferences
- **[INFERENCE] Laptop carrier block list:**
  - USB-C PD sink controller and a BQ25756 (or BQ25713) charger with power path to a 3S/4S pack.
  - A 5 V / 5 A buck for VCC_SOM.
  - VCCO LDOs or bucks (1.8 V and 3.3 V).
  - eDP connector driven from PS-GTR lanes by the PS DP controller, plus a backlight boost driver.
  - A USB 2.0 hub on the PS USB for keyboard and webcam.
  - The keyboard matrix scanned directly by PL HDIO (69 HDIO pins are plenty), which removes any USB dependency for the soft CPU.
  - I2C touchpad on PL HDIO.
  - A PL-driven 4-bit microSD slot or eMMC on HDIO.
  - Fan PWM and battery fuel gauge on I2C.
  - A power button routed to PWROFF_C2M_L and MIO31_SHUTDOWN logic.
- **[GUESS] Carrier cost** for a prototype of 2–5 units:
  - 8-layer, about 120 × 100 mm PCB: about $100–250 for 5.
  - Two Samtec connectors: about $50.
  - Other BOM parts: about $60–150.
  - Assembly: about $100–300 setup.

  That totals roughly **$300–700 for the first batch**, excluding the $325–420 SOM and excluding design time and respins. The eDP and GTR routing and the DDR-free design (DDR is on the SOM) keep it to 8 layers without HDI, as Antmicro shows.

### Gaps
- I could not fetch UG1091 itself (403). Its layer-stackup recommendations, VCC_SOM inrush and decoupling guidance, and keep-out details are not captured here.
- I did not confirm eDP-specific support (e.g., eDP 1.4 features, panel self-refresh) in the ZynqMP DP controller.

## 8. Rough BOM and costs (2025-2026)

### Takeaway
A KV260-based laptop built from off-the-shelf parts costs roughly **$450–650**. The cheapest route is a laptop shell: KV260 plus CrowView Note or NexDock plus a 12 V battery. A 3D-printed build with a separate panel and keyboard costs about the same and takes more work. A custom-carrier laptop starts around **$900–1,400+** for the first prototypes (SOM plus PCB plus parts), not counting engineering time.

### Cited Findings (unit prices)

| Item | Price (date) | Source |
|---|---|---|
| AMD KV260 SK-KV260-G | MSRP $249; distributors $275–294 (2026 snippet); DigiKey shipped the "2025 refresh" from Jul 2025 | [Octopart/DigiKey/Newark via search](https://www.digikey.com/en/products/detail/amd/SK-KV260-G/13985269); [DigiKey forum](https://forum.digikey.com/t/which-version-of-the-kria-sk-kv260-g-is-currently-available-the-new-25-refresh-or-the-original-21/57935) |
| 12 V 3 A PSU (CUI SMI36-12-V-P6 or equivalent) | not priced; **[GUESS]** ~$15–25 | [UG1089](https://docs.xibif.ch/_downloads/480ec1217d1ac2bd520e695148cfe86f/KV260_Userguide.pdf) |
| K26C SOM (custom-carrier route) | MSRP $325; $377–422 | [DigiKey](https://www.digikey.com/en/products/detail/amd/SM-K26-XCL2GC/13985266) |
| TalentCell 12 V 6000 mAh pack | ~$30–46 | [Amazon](https://us.amazon.com/Talentcell-Rechargeable-6000mAh-Battery-Portable/dp/B00MF70BPU) |
| USB-C PD 12 V trigger board | multi-packs; **[GUESS]** ~$2–5 each | [Amazon](https://www.amazon.com/Trigger-Module-Charge-Output-Delivery/dp/B0GWMWFXCG) |
| 14" FHD eDP panel driver board (HDMI to eDP) | $17–22 | [eBay](https://www.ebay.com/itm/167229239433) |
| 14" FHD eDP laptop panel (e.g., NV140FHM) | not priced; **[GUESS]** ~$40–70 used or new | — |
| Waveshare 13.3" FHD HDMI touch monitor | $145–210 | [Waveshare](https://www.waveshare.com/13.3inch-fhd-monitor.htm) |
| CrowView Note shell (screen, keyboard, touchpad, 37 Wh battery) | $129.9–169 | [CNX](https://www.cnx-software.com/2024/08/17/crowview-note-review-a-14-inch-laptop-shell-designed-for-raspberry-pi-5-and-jetson-nano-developer-kit/) |
| NexDock 6 / NexDock XL | $229 / $349 | [BigGo](https://biggo.com/news/202512171324_NexDock-6-Lapdock-Launch-Phone-to-Laptop) |
| MNT Pocket Reform standalone keyboard and trackball | €139 | [MNT shop](https://shop.mntre.com/products/mnt-pocket-reform-standalone-keyboard) |
| MNT Reform keyboard 4.0 / trackball / trackpad | €190–220 / €50 / €50 | [MNT shop](https://shop.mntre.com/products/mnt-reform-usb-keyboard-standalone) |
| Digilent Pmod PS2 / Pmod MicroSD | $8.99–10 / $7.86–8 | [Digilent](https://digilent.com/shop/pmod-ps2-keyboard-mouse-connector/) |
| Samtec ADM6-60 carrier connector ×2 | $19–28 each | [LCSC](https://www.lcsc.com/product-detail/C3649973.html) |
| 8-layer PCB ×5 (small) | from ~$82 | [JLCPCB](https://jlcpcb.com/impedance) |
| 3D-print filament, inserts, hinges, cables | not sourced; **[GUESS]** ~$30–60 | — |

### Inferences
- **[INFERENCE] Build A, "laptop shell":**
  - KV260 $280 + CrowView Note $130–169 + TalentCell $30 + PD trigger, cables and Pmod USB-A breakout about $20.
  - Total **about $460–500**.
  - Caveat: the shell's battery can't power the 12 V KV260, so two batteries are needed. The shell's keyboard and touchpad are USB, so the soft CPU still needs the PL USB-HID path or a PS bridge.
- **[INFERENCE] Build B, "3D-printed clamshell":**
  - KV260 $280 + eDP panel and driver board about $60–90 + MNT Pocket keyboard €139 (about $150) or a cheap USB mini keyboard (**[GUESS]** $20–40) + battery $30 + Pmods $18 + print and cables $50.
  - Total **about $480–650**.
- **[INFERENCE] Build C, "custom carrier":**
  - K26 SOM about $400 + carrier prototypes about $300–700 + panel and keyboard $100–250 + battery cells and BMS about $50.
  - Total about **$900–1,400** for the first unit, falling sharply at volume (SOM 1k-qty pricing was not found; the KV260 kit drops to $181.59 at 1000 units per a distributor snippet).

### Gaps
- I did not source prices for the bare eDP laptop panels, hinges, the 12 V PSU, or a low-cost USB laptop-style keyboard and touchpad module.
- There is no confirmed KV260 "2025 refresh" changelog; DigiKey only confirms it shipped.
