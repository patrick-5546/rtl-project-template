# top: parameterized counter

The template's example design: a counter with an enable and a synchronous,
active-low reset. Replace this spec, the RTL and its tests with your own design;
give each module a spec like this one in `docs/design/`.

## Parameters

| Name | Default | Description |
| --- | --- | --- |
| `WIDTH` | 8 | Width of the count; it counts from 0 to 2^`WIDTH` - 1. |

The named configurations in `tests/cocotb_configs.py`, `width4` and `width8`,
set `WIDTH` to 4 and 8.

## Ports

| Port | Direction | Width | Description |
| --- | --- | --- | --- |
| `clk_i` | input | 1 | Clock: the count changes only on its rising edge. |
| `rst_ni` | input | 1 | Synchronous reset, active low. |
| `en_i` | input | 1 | Count enable, active high. |
| `count_o` | output | `WIDTH` | The count. |

## Behavior

On each rising edge of `clk_i`:

1. While `rst_ni` is low, `count_o` becomes 0. Reset takes priority over the
   enable.
2. Otherwise, while `en_i` is high, `count_o` increments by one, wrapping from
   2^`WIDTH` - 1 to 0.
3. Otherwise, `count_o` holds its value.

`count_o` is unknown until the first rising edge with `rst_ni` low.

## Verification

`tests/test_top.py` runs these cocotb tests in each configuration:

| Test | Checks that |
| --- | --- |
| `reset_clears_counter` | reset clears the count at the next rising edge, not before |
| `enable_high_counts` | the count increments once per cycle while enabled |
| `enable_low_holds_count` | the count holds while the enable is low |
| `enable_low_holds_at_count` | the count holds in the mid, high and max ranges |
| `counter_wraps` | the count wraps from its maximum to 0 |

With `ABV=1`, `rtl/top_abv.sv` adds:

- assertions that reset clears the count, that a low enable holds it, and that
  a high enable increments it, each with a cover of its antecedent;
- covers of a hold, an increment, and a count at its maximum with the enable
  high;
- the covergroup `counter_cg`: the count in four ranges (low, mid, high and the
  maximum), the enable, the reset, and the enable crossed with the count range.

`make coverage DUT=top` collects these in each configuration;
`make waves DUT=top CONFIG=width8` opens the waveform with the layout in
`waves/`, which shows the 8-bit count.
