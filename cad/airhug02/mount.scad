// Millimetres. Camera front is -Y; ledge enters from +Y.
// Photo-informed revision; physical hardware fit remains untested.
// CAD reconstruction/prototype, not a measured manufacturer model.
part = "assembly"; // camera, clamp, screw, pad, coupon, assembly
$fn=64;
camera_w=70; camera_h=17.5; camera_d=25;
thread_slack=0.25; // radial: was 0.35; screw itself remains reusable
cradle_floor=70;
side_lip_height=10; // outer ends only; central 62 mm stays clear
print_offset=41; // maximum left/right clamp extent
corner_side=-1; // -1: left jamb stop; +1: right jamb; 0: no side stop
clearance=0.6; // total clearance of the optional nominal-body gauges
ledge_gap=30; jaw=10; throat=38; clamp_w=48;
// Coarse printable single-start trapezoidal thread, 16 mm major, 4 mm pitch.
module thread(length=38, slack=0) {
    pitch=4; root=6.6+slack; crest=8+slack;
    steps=ceil((length/pitch+2)*64);
    pts=[for(i=[0:steps], k=[0:3]) let(a=i*360/64, z=i*pitch/64-pitch,
        r=(k==0 || k==3)?root-0.1:crest,
        dz=k==0?-1.65:k==1?-0.25:k==2?0.25:1.65)
        [r*cos(a),r*sin(a),z+dz]];
    faces=concat([[3,2,1,0]],
        [for(i=[0:steps-1],k=[0:3],t=[0:1]) t==0 ? [i*4+k,i*4+(k+1)%4,(i+1)*4+(k+1)%4] : [i*4+k,(i+1)*4+(k+1)%4,(i+1)*4+k]],
        [[steps*4,steps*4+1,steps*4+2,steps*4+3]]);
    intersection() {
        cylinder(h=length,r=crest+0.1);
        union() { cylinder(h=length,r=root); polyhedron(points=pts,faces=faces,convexity=30); }
    }
}
module pill(w,h,d) { // capsule in XZ, depth Y
    rotate([90,0,0]) linear_extrude(d,center=true)
        hull() for(x=[-(w-h)/2,(w-h)/2]) translate([x,0]) circle(d=h);
}
module camera() {
    color("#25272b") pill(camera_w,camera_h,camera_d);
    color("#101114") translate([0,-camera_d/2-0.3,0]) pill(camera_w-2,camera_h-2,0.8);
    // Illustrative open privacy cover and exposed left lens; travel is not measured.
    color("#404348") translate([8,-camera_d/2-0.9,0]) pill(50,14,0.6);
    color("#08090a") translate([-26,-camera_d/2-1,0])
        rotate([90,0,0]) cylinder(h=0.8,d=6);
    color("#34363a") {
        translate([0,6,-13]) rotate([90,0,0]) cylinder(h=10,d=9,center=true);
        translate([-19,2,-23]) cube([38,30,4]);
        translate([-19,2,-27]) cube([38,30,4]);
    }
    // Cable exit, first 20 mm only (rest of flexible lead intentionally omitted).
    color("#17191b") translate([0,8,-4]) rotate([-70,0,0]) cylinder(h=20,d=3.5);
}
module cradle() {
    // Rectangular, open-top saddles do not depend on an exact capsule contour.
    // Clear width 76, toe-to-back depth 32. Centre stays open for the original clip/cable.
    for(s=[-1,1]) scale([s,1,1]) {
        difference() {
            translate([23,-19,cradle_floor-4]) cube([18,40,4]);
            // Through-slot lets the long tapered keeper descend below the floor.
            translate([25,8,cradle_floor-5]) cube([12,11,6]);
        }
        translate([23,-17,cradle_floor-1]) cube([18,3,1.6]); // 0.6 mm above floor, below bezel
        // Tall outer toes tie directly into the end stops. Recess the inner
        // face to Y=-16 to clear the illustrative projecting privacy cover.
        // Open top preserves drop-in assembly; these are bump stops, not latches.
        translate([31,-19,cradle_floor-1]) cube([10,3,side_lip_height+1]);
        translate([23,18,cradle_floor-4]) cube([18,3,28]); // rear guide
        translate([38,-19,cradle_floor-4]) cube([3,40,24]); // end stop
    }
}
module clamp_raw() {
    difference() {
        union() {
            translate([-clamp_w/2,0,-jaw]) cube([clamp_w,throat,jaw]);
            translate([-clamp_w/2,-jaw,-jaw]) cube([clamp_w,jaw,ledge_gap+2*jaw]);
            translate([-clamp_w/2,0,ledge_gap]) cube([clamp_w,throat,jaw]);
            if(corner_side!=0) translate([corner_side<0?-41:23,0,ledge_gap]) cube([18,28,15]);
            // Cantilevers connect the wide end saddles to the upper jaw.
            translate([-camera_w/2-2,-10,ledge_gap]) cube([camera_w+4,18,8]);
            for(s=[-1,1]) translate([s*(camera_w/2-7)-8,-12,ledge_gap]) cube([16,8,40]);
        }
        translate([0,24,-jaw-1]) thread(jaw+2,thread_slack);
    }
    cradle();
}
module clamp() {
    difference() {
        clamp_raw();
        // Original clip folds behind the head; leave its swept envelope clear.
        translate([-22.5,-3,ledge_gap+jaw+2]) cube([45,65,65]);
    }
}
module screw() {
    cylinder(h=6,d=30,$fn=12);
    translate([0,0,6]) thread(38);
    translate([0,0,44]) cylinder(h=2,d1=12.6,d2=10.5);
}
module pad() { // loose bearing pad; shallow socket on underside
    difference() {
        cylinder(h=5,d=27);
        translate([0,0,-0.1]) cylinder(h=2.5,d=17); // clear thread shoulder at full seating
    }
}
module key() {
    // Flat back at Y=0, 1..11 mm taper toward the camera over 36 mm.
    polyhedron(points=[[-5,-1,0],[5,-1,0],[5,0,0],[-5,0,0],
                       [-5,-11,36],[5,-11,36],[5,0,36],[-5,0,36]],
        faces=[[0,3,2,1],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]);
    translate([-6,-12,35]) cube([12,12,3]); // retrieval cap; back flush with guide
}
module coupon() { // short matching female thread + cradle cross-section
    difference() { cylinder(h=8,d=24); translate([0,0,-1]) thread(10,thread_slack); }
    translate([-35,32,0]) difference() {
        cube([camera_w+clearance+6,16,8]);
        translate([3,-1,3]) cube([camera_w+clearance,18,6]);
    }
    translate([24,0,0]) difference() {
        cube([18,camera_d+6,12]);
        translate([-1,3,3]) cube([20,camera_d+clearance,10]);
    }
}
if(part=="camera") camera();
if(part=="clamp") translate([0,0,print_offset]) rotate([0,-90,0]) clamp(); // side down, no jaw bridge
if(part=="screw") screw();
if(part=="pad") rotate([180,0,0]) translate([0,0,-5]) pad();
if(part=="key") translate([0,0,6]) rotate([0,90,0]) key();
if(part=="coupon") coupon();
if(part=="assembly") {
    color("#57a8bd") clamp();
    color("#e6aa51") translate([0,24,-38.6]) rotate([0,0,216]) screw();
    color("#edd7ae") translate([0,24,5]) pad();
    translate([0,-1.5,cradle_floor+camera_h/2]) camera();
    for(s=[-1,1]) color("#e6aa51") translate([s*31,18,67]) key();
    %translate([-70,0,10]) cube([140,100,20]);
}
