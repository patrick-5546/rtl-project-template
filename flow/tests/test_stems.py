from flow.stems import stems


def test_stems_list_each_module_and_instance() -> None:
    meta = {
        "files": {
            "a": {"filename": "<built-in>", "realpath": "<built-in>"},
            "g": {"filename": "rtl/top.sv", "realpath": "/project/rtl/top.sv"},
        }
    }
    tree = {
        "modulesp": [
            {
                "type": "MODULE",
                "name": "top",
                "addr": "(F)",
                "loc": "g,6:8,9:11",
                "stmtsp": [
                    {"type": "VAR", "name": "clk"},
                    {"type": "CELL", "name": "u_leaf", "modp": "(G)"},
                    {"type": "CELL", "name": "u_ip", "modp": "(Z)"},
                ],
            },
            {"type": "PACKAGE", "name": "$unit", "addr": "(E)", "loc": "a,0:0,0:0"},
            {"type": "MODULE", "name": "leaf", "addr": "(G)", "loc": "g,30:8,30:12"},
        ]
    }
    assert stems(meta, tree) == (
        "++ module top file /project/rtl/top.sv lines 6 - 9\n"
        "++ comp u_leaf type leaf parent top\n"
        "++ comp u_ip type UNKNOWN parent top\n"
        "++ module leaf file /project/rtl/top.sv lines 30 - 30\n"
    )
