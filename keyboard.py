import math
import sys
import os
from functools import partial
import json
from gen_configs import Config, Shape
from cadquery import Location as Loc, Vector as Vec


def get_key_hole_shape(config: Config) -> cq.Sketch:
    if config.notched:
        return cq.Sketch().rect(config.switchHoleSize, config.switchHoleSize)\
            .push([(0, 4.2545), (0, -4.2545)]).rect(config.switchHoleSize + 2 * 0.8128, 3.5001).clean()
    else:
        return cq.Sketch().rect(config.switchHoleSize, config.switchHoleSize)


def get_key_positions(config: Config) -> [(float, float)]:
    kc = []
    for x in range(config.nCols):
        for y in range(config.nRows):
            kc.append((x, y))

    if config.thumbKeys:
        for (x, y) in config.thumbKeys:
            kc.append((x, y))

    min_x = min(kc, key=lambda xy: xy[0])[0]
    n_cols = config.nCols - min_x

    if config.staggering:
        if len(config.staggering) <= n_cols:
            st = config.staggering + [0] * \
                (n_cols - len(config.staggering))
        else:
            st = config.staggering
    else:
        st = [0] * n_cols

    kp = {}
    for x, y in kc:
        kp[(x, y)] = (config.columnSpacing * x,
                      st[x - min_x] + config.rowSpacing * y)

    return kp


def rotate(config: Config, pt):
    ang = math.radians(config.angle)
    x, y = pt
    return (x * math.cos(ang) - y * math.sin(ang) + config.hOffset,
            x * math.sin(ang) + y * math.cos(ang))


def get_center(config: Config, kp):
    fc = list(filter(lambda xy: xy[0] == 0, kp.keys()))
    a = max(fc)
    b = min(fc)

    pts = [(kp[a][0] - config.columnSpacing / 2,
            kp[a][1] + config.rowSpacing / 2), kp[b]]
    pts = list(map(partial(rotate, config), pts))
    pts = pts + list(map(lambda xy: (-xy[0], xy[1]), pts))
    pts.sort()
    pts.append(pts[0])
    return cq.Sketch().polygon(pts)


def get_screw_holes_pos(config: Config, kp):
    rot = partial(rotate, config)
    lut = {rot(xy): xy for xy in kp.values()}

    fc = lut.keys()

    pts = []
    pts.append(max(fc, key=lambda xy: -xy[1]))
    pts.append(max(fc, key=lambda xy: xy[0]))
    pts.append(max(fc, key=lambda xy: xy[0] + xy[1]))
    pts.append(max(fc, key=lambda xy: (- xy[0] - 1) + xy[1]))
    if config.shape == Shape.HULL and config.split and config.mcu_footprint:
        pts.append(max(fc, key=lambda xy: -xy[0] - xy[1]))

    pts = [lut[xy] for xy in pts]

    ox = config.columnSpacing / 2 + 2
    oy = config.rowSpacing / 2 + 2
    offs = [(-ox, -oy), (ox, -oy), (ox, oy), (-ox, oy), (-ox, oy)]

    pts = [(px_ + ox_, py_ + oy_)
           for ((px_, py_), (ox_, oy_)) in zip(pts, offs)]

    if config.split and config.mcu_footprint:
        pts.append((pts[3][0] - config.mcu_footprint[0], pts[3][1]))
        if config.shape == Shape.HULL:
            if (pts[4][0] > pts[5][0]):
                pts.append((pts[5][0], pts[5][1] - config.mcu_footprint[1]))
                pts.pop(4)
        else:
            pts.append((pts[4][0], pts[4][1] - config.mcu_footprint[1]))
        # pts.pop(3)

    pts = list(map(rot, pts))
    pts = pts + list(map(lambda xy: (-xy[0], xy[1]), pts))
    return pts


def get_base(config: Config, kp, thickness, window=False):

    foot_x, foot_y = (config.columnSpacing / 2 + config.switchHoleSize, config.rowSpacing / 2 +
                      config.switchHoleSize) if config.shape == Shape.LEAN else (config.switchHoleSize, config.switchHoleSize)
    base = cq.Sketch()
    if config.split and config.mcu_footprint:
        x_offs = (
            config.mcu_footprint[0] + foot_x) / 2
        y_offs = max([v[1] for (k, v) in kp.items() if k[0] == 0]
                     ) + (foot_y - config.mcu_footprint[1]) / 2
        base = base.push(
            [(-x_offs, y_offs)]).rect(*config.mcu_footprint).reset()

    base = base.push(kp.values())
    if config.shape == Shape.LEAN:
        base = base.rect(foot_x, foot_y)\
            .faces().clean().vertices().fillet(2.5).faces()\
            .wires().offset(5).clean()
    elif config.shape == Shape.HULL:
        base = base.rect(foot_x, foot_y)\
            .faces().hull().clean().wires().offset(12)

    base = cq.Workplane().placeSketch(base).extrude(thickness)

    base = base.rotate((0, 0, 0), (0, 0, 1), config.angle).translate(
        (config.hOffset, 0))

    if not config.split:
        base = base.mirror('YZ', union=True).faces(">Z").workplane().placeSketch(
            get_center(config, kp)).extrude(-thickness)

    if window:
        win = cq.Sketch().push(kp.values()).rect(config.columnSpacing / 2 +
                                                 config.switchHoleSize, config.rowSpacing / 2 + config.switchHoleSize)
        win = win.clean().faces().vertices().fillet(1)
        win = cq.Workplane().placeSketch(win).extrude(thickness).rotate((0, 0, 0), (0, 0, 1), config.angle).translate(
            (config.hOffset, 0))
        if not config.split:
            win = win.mirror('YZ', union=True)
        base = base.cut(win)

    return base


def add_reinf(base, config: Config, kp, shp, thickness):
    reinf = cq.Workplane().pushPoints(shp).cylinder(2 * thickness, 4)
    reinf = reinf.intersect(get_base(config, kp, thickness))
    return base.union(reinf)


def get_keys(kp, key_shape):
    return cq.Workplane().pushPoints(kp.values()).placeSketch(key_shape).extrude(config.plateThickness)\
        .rotate((0, 0, 0), (0, 0, 1), config.angle).translate(
        (config.hOffset, 0))


def meshify(base, key_shape, kp, is_split):
    bbox = base.val().BoundingBox()
    thc = bbox.zmax - bbox.zmin
    r = 2.5
    mesh_th = 1

    base_frame = base.faces(">Z").wires().toPending(
    ).workplane().offset2D(-4).cutBlind('next')

    keys_ = get_keys(kp, key_shape.copy(
    ).reset().wires().offset(mesh_th).clean())
    if not is_split:
        keys_ = keys_.mirror('YZ', union=True)

    dx = 3 * r + 2 * math.cos(math.radians(60)) * mesh_th
    dy = r * math.sin(math.radians(60)) + 0.5 * \
        mesh_th * math.sin(math.radians(60))

    xn = (bbox.xmax - bbox.xmin) / dx
    yn = (bbox.ymax - bbox.ymin) / dy

    mesh_points = []

    for x in range(0, round(xn)):
        for y in range(0, round(yn)):
            x_s = 0 if (y % 2) == 0 else 1.5 * r + \
                math.cos(math.radians(60)) * mesh_th
            mesh_points.append(
                (bbox.xmin + (x * dx) + x_s, bbox.ymin + (y * dy)))

    mesh = cq.Workplane().pushPoints(mesh_points).polygon(
        6, r * 2).extrude(thc)

    return base.cut(mesh).union(base_frame).union(keys_)


def get_mcu_pcb(config):
    pcb_l, pcb_w, pcb_t = (53, 23, 1.5)
    # pcb_l, pcb_w, pcb_t = (53.5, 21, 1.5)

    pcb = cq.Workplane('ZX').sketch().slot(10.5 - 5, 5, angle=90.0).finalize().extrude(-1.0)\
            .workplane().sketch().slot(9.0 - 3.5, 3.5, angle=90.0).finalize().extrude(-8.0)\
            .workplane(3).move((3.5 + pcb_t) / 2, 0)\
            .rect(pcb_t, pcb_w).extrude(-pcb_l)

    pcb_cut1 = cq.Workplane('ZX').workplane(-2).move((3.5 + pcb_t) / 2, 0)\
        .rect(pcb_t, pcb_w).extrude(-(pcb_l - 1)).faces(">Z").wires().toPending().workplane().extrude(-4 * config.spacerThickness)

    pcb_base = pcb.faces('>Z').workplane(-pcb_t).move(0, -
                                                      2 - (pcb_l / 2)).rect(pcb_w + 10, pcb_l + 3).extrude(2 * pcb_t)

    pcb = pcb.union(pcb_cut1)

    return pcb, pcb_base


def generate(config: Config, odir='output', switch_mesh=False):
    kp = get_key_positions(config)
    shp_top = get_screw_holes_pos(config, kp)
    shp_bottom = [(-x, -y) for x, y in shp_top]

    base = get_base(config, kp, config.plateThickness)

    bottomPlate = base.faces(">Z").wires(
    ).toPending().workplane().offset2D(-6.2).extrude(0.5)
    cut = cq.Workplane().pushPoints(shp_top).cylinder(
        1.0, 4.2).translate((0, 0, config.plateThickness + 0.5))
    bottomPlate = bottomPlate.cut(cut)

    key_shape = get_key_hole_shape(config)
    keys = get_keys(kp, key_shape)

    if not config.split:
        keys = keys.mirror('YZ', union=True)

    spacerPlate = get_base(config, kp, config.spacerThickness).faces(">Z").wires(
    ).toPending().workplane().offset2D(-6).cutBlind('next')
    spacerPlate = add_reinf(spacerPlate, config, kp,
                            shp_top, config.spacerThickness)
    if config.cnc:
        spacerPlate = spacerPlate.faces(">Z").workplane().pushPoints(
            shp_top).hole(config.screwHoleDiameter)
    else:
        # counterbored holes for threaded inserts
        # TODO add dimensions for screws different than M3
        insert_len = 4
        spacerPlate = spacerPlate.faces("<Z").workplane().pushPoints(shp_bottom).cboreHole(
            config.screwHoleDiameter + 0.8, config.screwHoleDiameter + 1.2, 1, insert_len)
        spacerPlate = spacerPlate.faces("<Z").workplane().pushPoints(
            shp_bottom).hole(config.screwHoleDiameter, 6)

    if switch_mesh:
        switchPlate = meshify(
            base, key_shape, kp, config.split).cut(keys)
        if config.cnc:
            switchPlate = add_reinf(switchPlate, config, kp,
                                    shp_top, config.plateThickness)
    else:
        if config.cnc:
            switchPlate = base.cut(keys)
        else:
            reinf = cq.Sketch().rect(config.switchHoleSize + 4,
                                     config.switchHoleSize + 4).vertices().chamfer(2.0)
            reinfs = get_keys(kp, reinf)
            reinfs = reinfs.mirror('YZ', union=True)
            reinfPlate = base.cut(reinfs)
            switchPlate = base.union(reinfPlate.translate(
                (0, 0, -1))).faces("<Z[1]").edges().fillet(0.9)
            switchPlate = switchPlate.cut(keys)
            rot = partial(rotate, config)
            d = (config.spacerThickness - 0.5)
            ps = [kp[p] for p in filter(
                lambda p: p[0] > 0 and p[1] < config.nRows - 1, kp.keys())]
            switchPlate = switchPlate.union(cq.Workplane("XY").pushPoints([rot((x - 8.5, y + 9.5)) for x, y in ps]).cylinder(
                d, 1.5).translate((0, 0, -d / 2)).mirror('YZ', union=True))

    topPlate = get_base(config, kp, config.plateThickness, True)
    if config.cnc:
        topPlate = add_reinf(topPlate, config, kp,
                             shp_top, config.plateThickness)

    if config.cnc:
        bottomPlate = bottomPlate.faces(">Z").workplane().pushPoints(
            shp_top).hole(config.screwHoleDiameter - 0.1)
        switchPlate = switchPlate.faces(">Z").workplane().pushPoints(
            shp_top).hole(config.screwHoleDiameter)
        topPlate = topPlate.faces(">Z").workplane().pushPoints(
            shp_top).hole(config.screwHoleDiameter - 0.1)
        if config.split:
            bottomPlate = bottomPlate.mirror('YZ', union=True)
            topPlate = topPlate.mirror('YZ', union=True)
            switchPlate = switchPlate.mirror('YZ', union=True)
            spacerPlate = spacerPlate.mirror('YZ', union=True)

        assy = (
            cq.Assembly(bottomPlate, name='bottom',
                        color=cq.Color(0.023, 0.152, 0.776, 0.5))
            .add(spacerPlate, name='spacer', loc=Loc(Vec(0, 0, config.plateThickness)))
            .add(switchPlate, name='switch', loc=Loc(Vec(0, 0, config.plateThickness + config.spacerThickness)))
            .add(topPlate, name='top', loc=Loc(Vec(0, 0, 2 * config.plateThickness + config.spacerThickness)))
        )

        exp = bottomPlate.union(spacerPlate.translate((0, 0, config.plateThickness)))\
            .union(switchPlate.translate((0, 0, config.plateThickness + config.spacerThickness)))\
            .union(topPlate.translate((0, 0, 2 * config.plateThickness + config.spacerThickness)))

        bbottomPlate = base.faces(">Z").workplane().pushPoints(
            shp_top).hole(config.screwHoleDiameter - 1)
        if config.split:
            bbottomPlate = bbottomPlate.mirror('YZ', union=True)
        flat = bbottomPlate
        offset = 0

        for pp, p in zip([bbottomPlate, spacerPlate, switchPlate, topPlate],
                         [spacerPlate, switchPlate, topPlate]):
            s = pp.val()
            offset += s.BoundingBox().ymax - s.BoundingBox().ymin + 30
            flat = flat.union(p.translate((0, -offset, 0)))

        cq.exporters.export(flat, os.path.join(
            odir, '{}_flat.dxf'.format(config.name)))

    else:
        bottomPlate = bottomPlate.faces("<Z").edges().fillet(1.0)
        angle = math.degrees(math.atan(1.5 / 1.7))
        bottomPlate = bottomPlate.faces("<Z").workplane(
        ).pushPoints(shp_bottom).cskHole(config.screwHoleDiameter, 2 * config.screwHoleDiameter, 2 * angle, depth=None)

        # adhesive feet markers
        if config.split:
            pts = [(shp_bottom[0][0] - 8, shp_bottom[0][1] - 8), (shp_bottom[1][0] + 8,
                                                                  shp_bottom[1][1] - 8), (shp_bottom[2][0] + 8, shp_bottom[2][1] + 8), (shp_bottom[4][0] - 8, shp_bottom[4][1] + 8)]
        else:
            pts = [(shp_bottom[0][0] - 8, shp_bottom[0][1] - 8), (shp_bottom[1][0] + 8,
                                                                  shp_bottom[1][1] - 8), (shp_bottom[2][0] + 8, shp_bottom[2][1] + 8)]

        pts += [(-x, y) for x, y in pts]
        bottomPlate = bottomPlate.faces("<Z").pushPoints(pts).hole(10, 0.5)

        topPlate = topPlate.faces(">Z").edges().fillet(0.7)
        topPlate = spacerPlate\
            .union(switchPlate.translate((0, 0, config.spacerThickness)))\
            .union(topPlate.translate((0, 0, config.spacerThickness + config.plateThickness)))

        if not config.split:
            fs = spacerPlate.faces('+Y').all()
            fs.sort(key=lambda f: f.edges().val().Center().y)
            fs = list(filter(lambda f: math.isclose(
                f.edges().val().Center().x, 0.0, abs_tol=1e-09), fs))
            assert (len(fs) == 2)
            ys = fs[-1].edges().val().Center().y

            mcu_pcb, pcb_base = get_mcu_pcb(config)
            topPlate = topPlate.union(pcb_base.translate(
                (0, ys, (config.spacerThickness / 2) + config.plateThickness)))
            topPlate = topPlate.cut(mcu_pcb.translate(
                (0, ys, (config.spacerThickness / 2) + config.plateThickness)))

        if config.split:
            topPlate = topPlate.mirror('YZ', union=True)
            bottomPlate = bottomPlate.mirror('YZ', union=True)

        assy = (
            cq.Assembly(bottomPlate, name='bottom',
                        color=cq.Color(0.023, 0.152, 0.776, 0.5))
            .add(topPlate, name='top', loc=Loc(Vec(0, 0, config.plateThickness)))
        )
        exp = bottomPlate.union(topPlate.translate(
            (0, 0, config.plateThickness + 0.1)))

    opt = {
        "width": 1200,
        "height": 1200,
        "marginLeft": 10,
        "marginTop": 10,
        "showAxes": True,
        "projectionDir": (0.5, -0.5, 0.5),
        "strokeWidth": 0.5,
        "showHidden": False,
    }

    cq.exporters.export(exp, os.path.join(
        odir, '{}.svg'.format(config.name)), opt=opt)
    # cq.exporters.export(exp, os.path.join(odir, '{}.stl'.format(config.name)))
    # assy.save(os.path.join(odir, '{}.step'.format(config.name)))

    return exp, assy


# no arguments == CQ-Editor mode
if len(sys.argv) > 1:
    fn = sys.argv[-1].split(':')[-1]
else:
    fn = 'configs/atreus_52l_print_97a7fee.json'

with open(fn, 'r', encoding='utf-8') as f:
    def config(): return None
    config.__dict__ = json.loads(f.read())

    if config.split and config.mcu_footprint:
        config.hOffset += config.mcu_footprint[0]

    obj, assy = generate(config)
    if len(sys.argv) > 1:
        show_object(obj)
    else:
        show_object(assy)
