# CTUCAN Migen Wishbone wrapper

This repository contains a python package that wraps the
[CTUCAN FD IP-core](https://gitlab.fel.cvut.cz/canbus/ctucanfd_ip_core) into a
[Migen](https://github.com/m-labs/migen) module with a Wishbone interface, that
can be used with [LiteX SoC Builder](https://github.com/enjoy-digital/litex)
for creating custom SoC designs.

Additionally, this project can be used to generate the Verilog code of
the Wishbone wrapper and use it separately without any other dependencies.

## Repository structure

The diagram below presents the simplified structure of this repository and
includes the most important files and directories.

```
.
├── ctucan
│   ├── __init__.py
│   ├── utils
│   └── vhdl
│       └── ...
├── patches
├── requirements.txt
├── scripts
│   ├── generate_verilog_wrapper.py
│   └── generate_vhdl_sources.py
├── setup.py
├── tests
│   ├── test_ctucan.py
│   ├── test_integration.py
│   ├── top_test.v
│   └── ...
└── third-party
    └── ctucanfd_ip_core
```

* `ctucan/` - the main directory of the python package. The implementation of
  both the main CTUCAN and Wishbone wrapper modules can be found
  in the `__init__.py` file. The `vhdl/` directory inside the package
  contains the CTUCAN sources in the MIT version patched with custom changes
  (from the `patches/` directory). Useful functions not related directly
  with to the created Migen modules can be found in the `utils/` directory.

* `patches/` - contains custom changes made to the MIT version of the CTUCAN
  IP-core, that allow the core to be converted from VHDL to Verilog
  using GHDL.

* `requirements.txt` - the list of python packages necessary for the package
  development and running tests.

* `scripts/` - contains scripts that can be useful for package management
  or source code generation. The `generate_vhdl_sources.py` script is used
  for producing CTUCAN sources from the original repository, patching them,
  and writing back to the chosen directory. It can be used to recreate
  the contents of the `ctucan/vhdl` directory. Besides that, the
  `generate_verilog_wrapper.py` script can be used to produce sources of
  the wishbone wrapper for the CTUCAN IP-core.

* `tests/` - directory with functional and integration tests of the CTUCAN
  python package. The `top_test.v` file contains a top-level module used
  for functional tests, which are placed in the `test_ctucan.py` script.
  The `test_integration.py` file contains tests showing that the Migen modules
  from the package can correctly be used together with Migen and LiteX.

## Prerequisites

If the `vhdl` or the `external` variants of the created CTUCAN module are used,
`LiteX` and `Migen` are the only required dependencies. When using the `verilog`
variant, you will need also [yosys](https://github.com/YosysHQ/yosys),
[ghdl](https://github.com/ghdl/ghdl), and
[ghdl-yosys-plugin](https://github.com/ghdl/ghdl-yosys-plugin) installed on
your machine.

## Usage

It is possible to use the package with `LiteX` or for generating
the verilog sources of the Wishbone wrapper.

### Instantiating the CTUCAN module in LiteX's SoC

The CTUCAN module from this package can be used in the same way as any
other Migen module, except that all the registers are implemented in the
Verilog code and not as LiteX CSRs. Because of that, there is no need
for adding them separately. All you need to do is to create a dedicated
memory region for the CAN registers:

```python
# 1. Create main SoC module
soc = BaseSoC(
    sys_clk_freq=int(100e6),
    integrated_rom_size=0x20000
)

# 2. Instantiate the CTUCAN IP-core
can_pads = soc.platform.request("can")                       # get the can pads
soc.submodules.can = CTUCAN(soc.platform, can_pads, "vhdl")  # connect the IP-core with the main SoC
soc.add_interrupt("can")                                     # connect the IRQ line to the used CPU

# 3. Create a separate memory region for the CAN IP-core
soc.add_memory_region("can", None, soc.can.wbwrapper.size, type=[])
soc.add_wb_slave(soc.bus.regions["can"].origin, soc.can.wbwrapper.bus)
```
When building the LiteX design you should see the following information
in the generated log:

* The `can` memory region has been added as a slave:
```
Bus Slaves: (5)
- rom
- sram
- main_ram
- can
- csr
```

* The CTUCAN IRQ has been connected to the CPU:
```
IRQ Locations: (3)
- uart   : 0
- timer0 : 1
- can    : 2
```

### Generating Wishbone wrapper

To generate the Wishbone wrapper, you can use the dedicated script from the
`scripts` directory:

```bash
./generate_verilog_sources.py > ctucan_wrapper.v
```
Note that to use the wrapper, you will have to append the sources
of the CTUCAN IP-core itself.