// Animation only: use the committed meshes without rebuilding print artifacts.
// Render with animate_assembly.py. t runs from 0 to 6; camera clip is pre-folded.
use <mount.scad>
t=6;
function progress(stage) = min(1,max(0,t-stage));
slide=-58*(1-progress(2));
tight=progress(3);

// Example 20 mm ledge and left jamb. The upper jaw rests at z=30.
color("#c4c9d0") translate([-40,0,10]) cube([105,65,20]);
color("#a7afb9") translate([-49,0,30]) cube([9,65,33]);

translate([0,slide,0]) {
    color("#57a8bd") rotate([0,90,0]) translate([0,0,-40])
        import("stl/clamp.stl",convexity=20);
    // 4 mm per revolution; rotation preserves the thread phase as it advances.
    color("#e6aa51") translate([0,24,-75+30*progress(0)+6*tight])
        rotate([0,0,(-34+30*progress(0)+6*tight)*90])
        import("stl/screw.stl",convexity=20);
    if(t>1) color("#edd7ae")
        translate([52*(1-min(1,progress(1)*2)),24,
                   8-9*max(0,progress(1)*2-1)+6*tight])
        translate([0,0,5]) rotate([180,0,0]) import("stl/pad.stl");
}
if(t>4) translate([0,0,83+50*(1-progress(4))]) camera();
if(t>5) for(s=[-1,1]) color("#e6aa51")
    translate([s*25.5,5.3,78+35*(1-progress(5))])
    rotate([0,-90,0]) translate([0,0,-7]) import("stl/key.stl");
