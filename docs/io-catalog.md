# I/O catalogue

Status: **draft for review** (Phase 0). Decisions marked **[decide]** need the
owner.

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

## Four ways an interface is implemented

| kind | what it is | generated as | fabric cost |
|---|---|---|---|
| **PS hard peripheral** | a controller in the board's processing system (Zynq-7000, Zynq UltraScale+, Versal) | PS configuration enabling it; its register window and interrupt on the RISC-V's MMIO window and interrupt lines; firmware set-up on the RISC-V; a device-tree node for Linux's generic driver | glue only |
| **fabric hard block** | silicon in the FPGA fabric that is not a processor: PCIe blocks, multi-gigabit transceivers, memory controllers on Versal, I/O SERDES, clock managers | Vivado IP from the catalogue (Clocking Wizard, SelectIO, PCIe, transceiver wizards, MIG), configured by the generator | the IP's wrapper |
| **vendor soft IP** | an AMD IP core built from fabric logic (MIG for DDR on 7-series/UltraScale, Ethernet MACs, video subsystems) | Vivado IP from the catalogue, configured by the generator | the IP's size; some need a licence |
| **Ouroboros HLS IP** | an interface written in C++ for HLS, in this project | an HLS top, instantiated with the platform's parameters | as measured |

HLS cannot instantiate FPGA primitives directly: I/O SERDES, DDR flip-flops,
clock managers, transceivers. Where an interface needs one -- TMDS serialising
for HDMI, a DDR memory PHY, Ethernet's RGMII timing -- the generator configures
the vendor IP that wraps it, and the HLS logic sits beside it.

**[decide] Vendor IP counts as generated.** The all-HLS rule forbids
hand-written HDL. Vivado catalogue IP (MIG, Clocking Wizard, PCIe, SelectIO,
transceiver wizards, video and Ethernet subsystems) is configured by the
generator and its RTL produced by Vivado -- generated, not hand-written. This
catalogue assumes that reading, because several classes below cannot be built
without it on any AMD part. Licensed IP is marked; using it needs a licence
the user may not have, so an unlicensed alternative is listed where one exists.

## The catalogue

Tier: **1** = needed to boot Linux and use the machine on common boards;
**2** = common and useful; **3** = specialised. Linux binding is the
device-tree `compatible` family the generated node uses, so stock drivers bind.

### Memory

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| DDR behind a PS (Zynq, Versal) | PS hard peripheral: the PS memory controller, reached through PS-PL ports | memory | 1 |
| DDR3/DDR4/LPDDR4 on fabric pins | vendor soft IP: MIG (7-series, UltraScale); Versal: hard memory controller | memory | 1 |
| on-chip RAM (BRAM, URAM) | always present | memory or scratchpad | 1 |
| HBM (Virtex UltraScale+ HBM, Versal HBM) | fabric hard block | memory | 3 |
| QSPI / SPI flash | PS hard peripheral; Ouroboros HLS SPI controller (also boot flash) | `jedec,spi-nor` | 2 |

### Display

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| HDMI/DP from a PS DisplayPort controller (KV260, ZCU10x) | PS hard peripheral + Ouroboros HLS display engine feeding its live-video input | `simple-framebuffer` | 1 |
| HDMI/DVI on fabric pins (TMDS) | Ouroboros HLS display engine + TMDS encoder in HLS + vendor SelectIO/OSERDES for serialising (DVI-compatible HDMI 1.x, no licence); or AMD HDMI TX subsystem (**licensed**) | `simple-framebuffer` | 1 |
| HDMI through an encoder chip on the board (e.g. ADV7511, SiI9022) | HLS display engine driving parallel video + the chip's I2C set-up | `simple-framebuffer` | 1 |
| VGA (resistor DAC on fabric pins) | HLS display engine + sync generation | `simple-framebuffer` | 1 |
| DisplayPort on fabric transceivers | AMD DisplayPort TX subsystem (**licensed**) + transceiver | `simple-framebuffer` | 3 |
| MIPI DSI panels, LVDS/eDP panels | vendor IP (MIPI DSI TX, **licensed**); LVDS via SelectIO + HLS | `simple-framebuffer` | 3 |

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
| Ethernet with a PHY on fabric pins (MII/RMII/RGMII) | Ouroboros HLS MAC (reference: LiteEth, re-implemented) + vendor SelectIO for RGMII timing; or AMD Tri-Mode Ethernet MAC (**licensed**) | an Ouroboros MAC driver, or `xlnx,axi-ethernet` | 2 |
| SGMII / 10G and faster on transceivers | vendor IP (**licensed**) + transceiver | vendor driver | 3 |

### Audio, cameras, expansion

| interface | implementations | Linux sees | tier |
|---|---|---|---|
| audio codec (I2S + I2C control) | Ouroboros HLS I2S + I2C | ALSA simple-audio-card | 2 |
| MIPI CSI-2 cameras (KV260: three) | AMD MIPI CSI-2 RX subsystem (**licensed** on some parts) + Ouroboros HLS capture to memory | V4L2 | 2 |
| image signal processors on the board (KV260: AP1302) | the chip's I2C set-up | V4L2 subdevice | 3 |
| USB cameras | through the board's USB | UVC | 2 |
| PCIe (root port: NVMe, Wi-Fi, GPUs) | fabric hard block (PCIe IP) or PS PCIe (Zynq UltraScale+) | `pci-host-generic` / vendor | 3 |
| Pmod, FMC, Arduino/Raspberry Pi headers | pins: whatever is plugged in uses the rows above | per module | 2 |

### Clocks and reset

Every board has them, so they are never disabled: the generator finds the
board's clock sources (fabric oscillators, or the PS's fabric clocks on boards
like the KV260 that have none of their own) and configures Clocking Wizard IP
for the core's, the accelerator's and each interface's clock domain.

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

## Open

- **[decide]** Vendor IP from the Vivado catalogue counts as generated, not
  hand-written (above).
- **[decide]** Whether licensed vendor IP is allowed at all, or only the
  unlicensed alternatives.
- Exact device-tree `compatible` strings are to be checked against the Linux
  version Ouroboros boots; the families above are indicative.
- How the generator reads interfaces from board files for boards whose files
  describe less than the KV260's (many third-party board files list only a
  few interfaces).
