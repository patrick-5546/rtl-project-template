module top_abv #(
    parameter int unsigned WIDTH = 8
) (
    input logic clk_i,
    input logic rst_ni,
    input logic en_i,
    input logic [WIDTH-1:0] count_o
);

  localparam logic [WIDTH-1:0] MaxCount = {WIDTH{1'b1}};

  // Assertions

  reset_clears_counter_a :
  assert property (@(posedge clk_i) !rst_ni |=> count_o == '0)
  else $fatal("count_o did not clear after reset");

  enable_low_holds_counter_a :
  assert property (@(posedge clk_i) disable iff (!rst_ni) !en_i |=> count_o == $past(count_o))
  else $fatal("count_o changed while en_i was low");

  enable_high_increments_counter_a :
  assert property (@(posedge clk_i) disable iff (!rst_ni) en_i |=> count_o == $past(count_o) + 1'b1)
  else $fatal("count_o did not increment while en_i was high");

  // Coverage

  reset_observed_c :
  cover property (@(posedge clk_i) !rst_ni);

  enable_low_hold_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) $past(
      rst_ni
  ) && !$past(
      en_i
  ) && count_o == $past(
      count_o
  ));

  enable_high_increment_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) $past(
      rst_ni
  ) && $past(
      en_i
  ) && count_o == $past(
      count_o
  ) + 1'b1);

  wraparound_setup_observed_c :
  cover property (@(posedge clk_i) disable iff (!rst_ni) en_i && count_o == MaxCount);

endmodule
