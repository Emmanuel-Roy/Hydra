# I/O catalogue

Status: **draft for review** (Phase 0).

Ouroboros has to build around whatever a board offers -- any FPGA, not just
the KV260 (decisions, 2026-10-01). The generator ([platform-generator.md](platform-generator.md))
reads a board's interfaces from its platform specification and, for each one
the user enables, generates support from this catalogue. The catalogue is
organised by **what drives an interface**, never by board: support an
implementation once and every board that has it is covered.

## Scope: any FPGA the tools target

Everything is built with Vitis HLS and Vivado, so "any FPGA" means **any AMD
part the pinned AMD release supports**: Spartan-7, Artix-7, Kintex-7, Virtex-7,
Kintex/Virtex UltraScale and UltraScale+, Zynq-7000, Zynq UltraScale+ (as on
the KV260), Versal. Boards with and without a hard processing system are both
in scope; without one, the generator's output is smaller, not different in
kind. Other vendors' FPGAs (Intel/Altera, Lattice, Efinix, Gowin, Microchip)
need a different HLS toolchain and are out of scope.

## Ouroboros's own IP, on the silicon

Ouroboros aims to use **100% its own IP** (decisions, 2026-10-01). Every piece
of logic in the FPGA -- the core, the uncore, the accelerator, every
interface -- is Ouroboros's own C++ for HLS. What is not logic is the silicon
itself, which no IP can replace and HLS cannot express:

| silicon | examples | reached through |
|---|---|---|
| the processing system, where there is one | Zynq-7000 PS, Zynq UltraScale+ PS (owns the KV260's DDR, clocks, boot and PC peripherals), Versal CIPS | the PS block, configured by the generator from the board preset; its hard peripherals are silicon too, driven by Ouroboros firmware on the RISC-V |
| clock managers | MMCM, PLL | the thinnest generated wrapper, one primitive per clock domain |
| I/O primitives | input/output SERDES, DDR registers, delays, differential buffers, native MIPI D-PHY I/O | the thinnest generated wrapper, beside the HLS logic that drives them |
| transceivers | GTP/GTX/GTH/GTY | the thinnest generated wrapper |
| fabric hard blocks | PCIe blocks, Versal's hard memory controllers, XADC/SYSMON | the thinnest generated wrapper |
| memories and DSPs | BRAM, URAM, DSP48 | inferred by HLS from the C++ -- no wrapper at all |

"Thinnest wrapper" means the primitive and nothing else: no vendor logic
around it, no licence. Everything the primitive's own documentation leaves to
the designer -- calibration, protocol, framing -- is Ouroboros's HLS.

**Vendor soft IP is a stopgap, never a destination.** Where an interface
cannot yet be built from Ouroboros IP on primitives, vendor soft IP may stand
in, listed in **Stopgaps** below with the Ouroboros block that replaces it. A
build that uses one says so. **Licensed IP is never used.**

## How an interface is implemented

| kind | what it is | generated as | fabric cost |
|---|---|---|---|
| **PS hard peripheral** | a controller in the board's processing system (Zynq-7000, Zynq UltraScale+, Versal) | PS configuration enabling it; its register window and interrupt on the RISC-V's MMIO window and interrupt lines; Ouroboros firmware on the RISC-V; a device-tree node for Linux's generic driver | glue only |
| **Ouroboros HLS IP on primitives** | the interface's logic in C++ for HLS, beside the silicon primitives it needs | an HLS top, instantiated with the platform's parameters, and the primitives' thinnest wrappers | as measured |
| **stopgap** | vendor soft IP standing in until the Ouroboros block exists | Vivado catalogue IP | the IP's size |

## The catalogue

Tier: **1** = needed to boot Linux and use the machine on common boards;
**2** = common and useful; **3** = specialised. Linux binding is the
device-tree `compatible` family the generated node uses, so stock drivers bind.

### Memory

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| DDR behind a PS (Zynq, Versal) | PS hard peripheral: the PS memory controller, reached through PS-PL ports | memory | 1 |
| DDR3/DDR4/LPDDR4 on fabric pins | Ouroboros HLS DDR controller, PHY logic and calibration on the I/O primitives (stopgap: MIG); Versal: its hard memory controller | memory | 1 |
| on-chip RAM (BRAM, URAM) | always present | memory or scratchpad | 1 |
| HBM (Virtex UltraScale+ HBM, Versal HBM) | fabric hard block | memory | 3 |
| QSPI / SPI flash | PS hard peripheral; Ouroboros HLS SPI controller (also boot flash) | `jedec,spi-nor` | 2 |

### Display

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| HDMI/DP from a PS DisplayPort controller (KV260, ZCU10x) | PS hard peripheral + Ouroboros HLS display engine feeding its live-video input | `simple-framebuffer` | 1 |
| HDMI/DVI on fabric pins (TMDS) | Ouroboros HLS display engine + HLS TMDS encoder, on output SERDES primitives (DVI-compatible HDMI 1.x) | `simple-framebuffer` | 1 |
| HDMI through an encoder chip on the board (e.g. ADV7511, SiI9022) | HLS display engine driving parallel video + the chip's I2C set-up | `simple-framebuffer` | 1 |
| VGA (resistor DAC on fabric pins) | HLS display engine + sync generation | `simple-framebuffer` | 1 |
| DisplayPort on fabric transceivers | Ouroboros HLS DisplayPort source (link layer, training) on a transceiver primitive | `simple-framebuffer` | 3 |
| MIPI DSI panels, LVDS/eDP panels | Ouroboros HLS DSI or LVDS transmitter on D-PHY / output SERDES primitives | `simple-framebuffer` | 3 |

The display engine is the same HLS C++ on every board: it scans a framebuffer
out of memory with the platform's video timing. Only what it feeds differs.

### Input

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| USB keyboard/mouse through a PS USB controller | PS hard peripheral (DWC3 on Zynq UltraScale+, ChipIdea on Zynq-7000) | `snps,dwc3` / `xlnx,zynq-usb` | 1 |
| USB HID on fabric pins (low/full speed, no PHY) | Ouroboros HLS USB HID host (reference: nand2mario's, re-implemented in C++) | an Ouroboros keyboard/mouse device | 1 |
| USB through a ULPI PHY on the board | Ouroboros HLS ULPI link + USB host (larger) | USB host | 3 |
| PS/2 keyboard/mouse (including boards that bridge USB to PS/2, e.g. Digilent's) | Ouroboros HLS PS/2 controller | `altr,ps2-1.0`-style or an Ouroboros node | 1 |
| buttons, switches, rotary encoders | Ouroboros HLS GPIO | `gpio-keys` | 2 |
| touch panels (I2C) | HLS I2C controller | the panel's driver over I2C | 3 |

### Storage

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| SD/microSD through a PS controller | PS hard peripheral (SDHCI) | `arasan,sdhci-*` / SDHCI | 1 |
| SD on fabric pins, SPI mode | Ouroboros HLS SPI controller | `mmc-spi-slot` | 1 |
| SD on fabric pins, 4-bit native | Ouroboros HLS SD host (reference: LiteSDCard, re-implemented) | SDHCI-compatible or an Ouroboros node | 2 |
| eMMC through a PS controller | PS hard peripheral | SDHCI | 2 |
| SATA, NVMe | PS SATA (Zynq UltraScale+); NVMe over PCIe | AHCI / NVMe | 3 |

### Serial and low-speed

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| UART (console, usually through a USB-UART bridge on the board) | PS UART; Ouroboros HLS UART (part of the uncore) | `ns16550a` | 1 |
| GPIO, LEDs, seven-segment displays | Ouroboros HLS GPIO | `gpio-leds`, GPIO | 1 |
| fan PWM, other PWM | Ouroboros HLS PWM | `pwm-fan` | 1 when the board has a fan |
| I2C | PS I2C; Ouroboros HLS I2C | `i2c-*` | 2 |
| SPI | PS SPI; Ouroboros HLS SPI | `spi-*` | 2 |
| CAN | PS CAN (Zynq) | `xlnx,zynqmp-can-1.0` | 3 |
| on-chip temperature and voltage (XADC, SYSMON) | fabric hard block, read over its interface | `iio` hwmon | 2 |

### Networking

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| Ethernet through a PS MAC (GEM) | PS hard peripheral | `cdns,*-gem` / `xlnx,zynqmp-gem` | 2 |
| Ethernet with a PHY on fabric pins (MII/RMII/RGMII) | Ouroboros HLS MAC (reference: LiteEth, re-implemented) on DDR-register and delay primitives for RGMII timing | an Ouroboros MAC driver | 2 |
| SGMII / 10G and faster on transceivers | Ouroboros HLS PCS and MAC on a transceiver primitive | an Ouroboros MAC driver | 3 |

### Audio, cameras, expansion

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| audio codec (I2S + I2C control) | Ouroboros HLS I2S + I2C | ALSA simple-audio-card | 2 |
| MIPI CSI-2 cameras (KV260: three) | Ouroboros HLS CSI-2 receiver and capture to memory, on native D-PHY I/O or input SERDES primitives | V4L2 | 2 |
| image signal processors on the board (KV260: AP1302) | the chip's I2C set-up | V4L2 subdevice | 3 |
| USB cameras | through the board's USB | UVC | 2 |
| PCIe (root port: NVMe, Wi-Fi, GPUs) | the fabric's PCIe hard block (thinnest wrapper) with Ouroboros HLS bridging, or PS PCIe (Zynq UltraScale+) | `pci-host-generic` | 3 |
| Pmod, FMC, Arduino/Raspberry Pi headers | pins: whatever is plugged in uses the rows above | per module | 2 |

### Clocks and reset

Every board has them, so they are never disabled: the generator finds the
board's clock sources (fabric oscillators, or the PS's fabric clocks on boards
like the KV260 that have none of their own) and generates one MMCM or PLL per
clock domain -- the core's, the accelerator's, each interface's -- through its
thinnest wrapper.

## Resource accounting

Every implementation in the catalogue has a resource estimate (LUTs, FFs,
BRAM, DSPs, memory-port bandwidth), measured when it is first built and
stored with it. The configurator sums the enabled interfaces, subtracts them
from the target's resources, and gives the rest to the systolic array (the
"switch" rule in [platform-generator.md](platform-generator.md)).

## Order of work

1. **Tier 1 for the KV260**: PS DDR, the PS DisplayPort controller with the
   display engine, PS USB, PS SD, the UART, GPIO and the fan.
2. **Tier 1 for boards without a PS**, chosen to cover the other
   implementation kinds: MIG DDR, fabric HDMI/DVI or VGA, PS/2 or USB HID on
   pins, SD over SPI -- e.g. a Genesys 2 or an Arty.
3. Tier 2, by demand. Tier 3, as boards need it.

## Stopgaps

Vendor soft IP that may stand in, and what replaces it. A stopgap is a known
debt: every build that uses one reports it, and the list should only shrink.

| stopgap | used for | replaced by | why it is hard |
|---|---|---|---|
| MIG | DDR on fabric pins (boards without a PS: Genesys 2, Arty) | Ouroboros HLS DDR controller, PHY logic and calibration | read/write levelling and per-bit deskew on the I/O primitives; LiteDRAM shows it can be done outside the vendor IP |

No other stopgap is planned: every other interface above is Ouroboros IP on
primitives from the start. The KV260 needs none -- its DDR is the PS's.

## Open

- What the thinnest wrapper is for each primitive, generated how: Vivado
  block-design utility cells, or primitive instances in the generated
  top-level wrapper. Neither is hand-written; which the pinned release
  supports for each primitive is a Phase 2 check.
- Exact device-tree `compatible` strings are to be checked against the Linux
  version Ouroboros boots; the families above are indicative.
- How the generator reads interfaces from board files for boards whose files
  describe less than the KV260's (many third-party board files list only a
  few interfaces).
