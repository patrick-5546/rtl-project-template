onerror {resume}
quietly WaveActivateNextPane {} 0
add wave -noupdate /top/clk_i
add wave -noupdate /top/rst_ni
add wave -noupdate /top/en_i
add wave -noupdate -radix hexadecimal /top/count_o
TreeUpdate [SetDefaultTree]
WaveRestoreCursors {{Cursor 1} {80 ns} 0}
quietly wave cursor active 1
configure wave -namecolwidth 150
configure wave -valuecolwidth 100
configure wave -justifyvalue left
configure wave -signalnamewidth 1
configure wave -snapdistance 10
configure wave -datasetprefix 0
configure wave -rowmargin 4
configure wave -childrowmargin 2
configure wave -gridoffset 0
configure wave -gridperiod 1
configure wave -griddelta 40
configure wave -timeline 0
configure wave -timelineunits ps
update
WaveRestoreZoom {0 ns} {276 ns}
