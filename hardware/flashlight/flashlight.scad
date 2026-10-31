// Video-derived Duracell 1600 flashlight and removable optical covers. Millimetres.
// Open in OpenSCAD, change part/mount/aperture, F6, export STL.
part = "assembly"; // reference, cover, coupon, disk, assembly, lineup
mount = "flex"; // flex, press, strap
aperture = "circle"; // circle, square, triangle, cross, filled
head_d = 40;       // MEASURE across highest groove lands before printing
head_length = 52;
length = 165;
body_d = 30;
clearance = 0.30;  // DIAMETRAL: negative = interference
wall = 1.6;
skirt = 14;
face = 1.2;
membrane = 0.20;   // exactly one 0.20 mm sliced layer
slot = 1.0;
$fn = 128;
eps = 0.02;
bore = head_d + clearance;
outer = bore + 2*wall;
plate = aperture == "filled" ? membrane : face;
assert(bore > 0 && wall > 0 && plate > 0 && skirt > 4);
assert(part == "reference" || part == "assembly" || part == "lineup" || part == "cover" || part == "coupon" || part == "disk");
assert(mount == "flex" || mount == "press" || mount == "strap");
assert(aperture == "circle" || aperture == "square" || aperture == "triangle" || aperture == "cross" || aperture == "filled");

module opening(shape=aperture) {
    // Equal nominal open area (about 314 mm²) for useful brightness comparisons.
    if(shape == "circle") circle(d=20);
    if(shape == "square") square([17.72,17.72],center=true);
    if(shape == "triangle") polygon([[0,15.55],[-13.47,-7.78],[13.47,-7.78]]);
    if(shape == "cross") union() {
        square([26,7],center=true); square([7,26],center=true);
    }
}
module shell(shape=aperture, h=skirt, base=plate) {
    difference() {
        cylinder(d=outer,h=h+base);
        // Bore stops on face: print closed face down, skirt up; no supports.
        translate([0,0,base]) cylinder(d=bore,h=h+eps);
        // Entry bevel removes material at the open end only.
        translate([0,0,base+h-1]) cylinder(d1=bore,d2=bore+1.2,h=1+eps);
        if(shape != "filled") translate([0,0,-eps])
            linear_extrude(base+2*eps) opening(shape);
        if(mount != "press") for(a=[0:90:270]) rotate([0,0,a])
            translate([bore/2-1,-slot/2,base+3]) cube([wall+3,slot,h]);
        // Recessed external band channel; leaves >=1 mm wall with defaults.
        if(mount == "strap") translate([0,0,base+h-5]) difference() {
            cylinder(d=outer+2,h=3); cylinder(d=outer-1.2,h=3);
        }
    }
}
module cover(shape=aperture) { shell(shape=shape, base=shape == "filled" ? membrane : face); }
module coupon() {
    // Same bore, mouth bevel, slot width and skirt wall as the cover, no face.
    difference() {
        cylinder(d=outer,h=8);
        translate([0,0,-eps]) cylinder(d=bore,h=8+2*eps);
        translate([0,0,7]) cylinder(d1=bore,d2=bore+1.2,h=1+eps);
        if(mount != "press") for(a=[0:90:270]) rotate([0,0,a])
            translate([bore/2-1,-slot/2,3]) cube([wall+3,slot,6]);
    }
}
module reference(show_lens=true) {
    // Origin = front bezel plane; +Z points toward tail. External envelope only.
    color([.12,.12,.13]) difference() {
        union() {
            cylinder(d1=head_d-1,d2=head_d,h=2);
            translate([0,0,2]) cylinder(d=head_d,h=head_length-10);
            translate([0,0,head_length-8]) cylinder(d1=head_d,d2=body_d,h=8);
            translate([0,0,head_length-eps]) cylinder(d=body_d,h=length-head_length+eps);
        }
        // Six shallow longitudinal flutes visible in rotating close-ups.
        for(a=[0:60:300]) rotate([0,0,a])
            translate([head_d/2+2,0,-eps]) cylinder(r=3,h=head_length-10,$fn=24);
        translate([0,0,-eps]) cylinder(d=head_d-5,h=6);
        // Tail-cap flutes and a shallow head/neck seam, visually estimated.
        for(a=[0:60:300]) rotate([0,0,a])
            translate([body_d/2+1.5,0,length-19]) cylinder(r=2,h=17,$fn=24);
        translate([0,0,head_length-8]) difference() {
            cylinder(d=head_d+1,h=.6); cylinder(d=head_d-1,h=.6);
        }
        // Grip rings and longitudinal channels, approximate cosmetic geometry.
        for(z=[78:5:139]) translate([0,0,z]) difference() {
            cylinder(d=body_d+1,h=.7); cylinder(d=body_d-1,h=.7);
        }
        for(a=[0:30:330]) rotate([0,0,a]) translate([body_d/2+.6,0,78])
            cylinder(r=1.1,h=62,$fn=12);
    }
    color("silver") translate([0,0,2]) difference() {
        cylinder(d=head_d-5,h=2); cylinder(d1=head_d-9,d2=8,h=2+eps);
    }
    // Previews can hide the lens to expose illustrative reflector and LED.
    if(show_lens) color([.65,.8,.88]) translate([0,0,1.8]) difference() {
        cylinder(d=head_d-7,h=1.4); cylinder(d=head_d-9,h=1.4+eps);
    }
    color("gold") translate([0,0,2.8]) cylinder(d=4,h=3.3);
    color([.75,.39,.21]) translate([0,0,length-24]) cylinder(d=body_d+.2,h=4);
    // Side switch normal to +X, visible in the side and oblique video poses.
    color([.18,.18,.18]) translate([body_d/2-1,0,head_length+10])
        rotate([0,90,0]) cylinder(d=12,h=2);
}
if(part == "reference") reference();
if(part == "cover") cover();
if(part == "coupon") coupon();
if(part == "disk") cylinder(d=head_d+clearance-0.5,h=membrane);
if(part == "assembly") {
    reference();
    color([.1,.5,.85,.8]) translate([0,0,-plate-1]) cover();
}
if(part == "lineup") for(i=[0:4]) translate([i*52,0,0])
    cover(shape=["circle","square","triangle","cross","filled"][i]);

// Module usable by the repeatable preview renderer.
module preview_lineup() {
    for(i=[0:4]) translate([i*52,0,0])
        cover(shape=["circle","square","triangle","cross","filled"][i]);
}
