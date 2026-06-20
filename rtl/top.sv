// top: parameterized counter with synchronous active-low reset and enable.
//
// On each rising clk_i edge: count_o clears to zero when rst_ni is asserted
// (low), increments by one when en_i is high, and otherwise holds its value.
// It wraps from all-ones back to zero. WIDTH sets the output width.
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
