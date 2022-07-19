#!/usr/bin/env python3

import os
import subprocess
import tempfile


def convert_to_verilog(
    srcs, dest, top_module, ghdl_flags=[], yosys_cmds=[], library=None
):
    srcs_abs = [os.path.abspath(f) for f in srcs]
    library_str = "" if library is None else f"--work={library}"

    ys = """
    ghdl {ghdl_flags} {vhdl_library} {sources_list} -e {top_module}
    {yosys_cmds}
    write_verilog {output_file}
    """.format(
        ghdl_flags=" ".join(ghdl_flags),
        vhdl_library=library_str,
        sources_list=" ".join(srcs_abs),
        yosys_cmds="\n".join(yosys_cmds),
        top_module=top_module,
        output_file=dest
    )

    with tempfile.NamedTemporaryFile("w") as ys_file:
        ys_file.write(ys)
        subprocess.check_call(f"cat {ys_file.name}", shell=True)
        ys_cmd = "yosys -m ghdl -s {}".format(ys_file.name)
        subprocess.check_call(ys_cmd, shell=True)


def collect_sources(directory, ext, absolute=True):
    files = [f for f in os.listdir(directory)]

    sources = []
    for f in files:
        file_path = os.path.join(directory, f)
        if os.path.isfile(file_path) and f.endswith(ext):
            if absolute:
                sources.append(os.path.abspath(file_path))
            else:
                source.append(os.path.normpath(file_path))

    return sources
