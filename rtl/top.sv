// top: parameterized counter with synchronous active-low reset and enable.
// Its specification is docs/design/top.md.
//
// With `+define+ABV`, top_abv.sv is `include`d to add SVA assertions and a
// covergroup over this module's signals.
module top #(
    parameter int unsigned WIDTH = 8
) (
    input logic clk_i,
    input logic rst_ni,
    input logic en_i,
    output logic [WIDTH-1:0] count_o
);

  always_ff @(posedge clk_i) begin
    if (!rst_ni) begin
      count_o <= '0;
    end else if (en_i) begin
      count_o <= count_o + 1'b1;
    end
  end

`ifdef ABV
  `include "top_abv.sv"
`endif

endmodule
