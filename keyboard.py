from cadquery import Assembly, Color, Location as Loc, Vector as Vec
from typing import Optional
import math
from functools import partial
from enum import Enum
import subprocess
import os


class Shape(Enum):
    LEAN = 1
    HULL = 2


class Config:
    nRows: int
    nCols: int
    thumbKeys: Optional[list]
    columnSpacing: float
    rowSpacing: float
    staggering: Optional[list]
    switchHoleSize: float
    angle: float  # degrees
    hOffset: float
    plateThickness: float
    shape: Shape
    screwHoleDiameter: float
    spacerThickness: float
    split: bool

    def __init__(self, nc, nr, cs=19, rs=19, switchHoleSize=13.97,
                 angle=10, hOffset=None, plateThickness=1.5,
                 spacerThickness=8.0, screwHoleDiameter=4.0,
                 shape=Shape.LEAN, split=False,
                 staggering=[0, 5, 11, 6, 3],
                 thumbKeys=None,
                 cnc=False,
                 notched=True,
                 ):
        self.nCols = nc
        self.nRows = nr
        self.angle = angle
        self.columnSpacing = cs
        self.rowSpacing = rs
        self.switchHoleSize = switchHoleSize
        if not hOffset:
            self.hOffset = (self.nRows * self.rowSpacing *
                            math.sin(math.radians(self.angle))) + 20
            if self.hOffset < 35:
                self.hOffset = 35
        else:
            self.hOffset = hOffset
        self.plateThickness = plateThickness
        self.spacerThickness = spacerThickness
        self.screwHoleDiameter = screwHoleDiameter
        self.shape = shape
        self.split = split
        self.staggering = staggering
        self.thumbKeys = thumbKeys
        self.cnc = cnc
        self.notched = notched
        self.update_name()

    def update_name(self):
        self.name = 'atreus_{}{}_{}'.format(
            2 * (self.nCols * self.nRows +
                 (len(self.thumbKeys) if self.thumbKeys else 0)),
            ('h' if self.shape == Shape.HULL else 'l') +
            ('s' if self.split else ''),
            'cnc' if self.cnc else 'print')


configs = [
    # some minimal configs :)
    Config(3, 3, angle=5),
    Config(4, 4, angle=5),

    # the original
    Config(5, 4),

    # my favourite config
    Config(6, 4, angle=18.5,
           staggering=[0, 5, 11, 6, 3, 2],
           thumbKeys=[(0, -1), (-1, 0)]),

    # # some bigger edge case :)
    # Config(10, 10, angle=18.5,
    #        staggering=[0, 5, 11, 6, 3, 2],
    #        thumbKeys=[(0, -1), (-1, 0)])
]


def get_key_hole_shape(config: Config) -> cq.Sketch:
    if config.notched:
        return cq.Sketch().rect(config.switchHoleSize, config.switchHoleSize)\
            .push([(0, 4.2545), (0, -4.2545)]).rect(config.switchHoleSize + 2 * 0.8128, 3.5001).clean()
    else:
        return cq.Sketch().rect(config.switchHoleSize, config.switchHoleSize)


def get_key_positions(config: Config) -> [(float, float)]:
    if config.staggering:
        if len(config.staggering) <= config.nCols:
            st = config.staggering + [0] * \
                (config.nCols - len(config.staggering))
        else:
            st = config.staggering
    else:
        st = [0] * config.nCols

    kp = {}
    for i, c in enumerate(range(config.nCols)):
        for r in range(config.nRows):
            kp[(c, r)] = (config.columnSpacing * c,
                          st[i] + config.rowSpacing * r)

    if config.thumbKeys:
        for (tx, ty) in config.thumbKeys:
            kp[(tx, ty)] = (config.rowSpacing * tx,
                            config.columnSpacing * ty)

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
    fc = kp.keys()
    pts = []

    pts.append(max(fc, key=lambda xy: (config.nRows -
               xy[0] - 1) + (config.nCols - xy[1] - 1)))
    pts.append(max(fc, key=lambda xy: xy[0] + (config.nCols - xy[1] - 1)))
    pts.append(max(fc))
    pts.append(max(fc, key=lambda xy: (config.nRows - xy[0] - 1) + xy[1]))

    pts = [kp[k] for k in pts]

    ox = config.columnSpacing / 2 + 2
    oy = config.rowSpacing / 2 + 2
    offs = [(-ox, -oy), (ox, -oy), (ox, oy), (-ox, oy)]

    pts = [(px_ + ox_, py_ + oy_)
           for ((px_, py_), (ox_, oy_)) in zip(pts, offs)]

    pts = list(map(partial(rotate, config), pts))
    pts = pts + list(map(lambda xy: (-xy[0], xy[1]), pts))
    return pts


def get_base(config: Config, kp, thickness, window=False):

    base = cq.Sketch().push(kp.values())
    if config.shape == Shape.LEAN:
        base = base.rect(config.columnSpacing / 2 + config.switchHoleSize, config.rowSpacing / 2 + config.switchHoleSize)\
            .faces().clean().vertices().fillet(2.5).faces()\
            .wires().offset(5).clean()
    elif config.shape == Shape.HULL:
        base = base.rect(config.switchHoleSize, config.switchHoleSize)\
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


def generate(config: Config, odir='output'):
    kp = get_key_positions(config)
    shp = get_screw_holes_pos(config, kp)

    bottomPlate = get_base(config, kp, config.plateThickness).faces(">Z").wires(
    ).toPending().workplane().offset2D(-6.2).extrude(0.5)
    cut = cq.Workplane().pushPoints(shp).cylinder(
        1.0, 4.2).translate((0, 0, config.plateThickness + 0.5))
    bottomPlate = bottomPlate.cut(cut)
    bottomPlate = bottomPlate.faces(">Z").workplane().pushPoints(
        shp).hole(config.screwHoleDiameter - 1)

    key_shape = get_key_hole_shape(config)
    keys = cq.Workplane().pushPoints(kp.values()).placeSketch(key_shape).extrude(config.plateThickness)\
        .rotate((0, 0, 0), (0, 0, 1), config.angle).translate(
        (config.hOffset, 0))

    if not config.split:
        keys = keys.mirror('YZ', union=True)

    spacerPlate = get_base(config, kp, config.spacerThickness).faces(">Z").wires(
    ).toPending().workplane().offset2D(-6).cutBlind('next')
    spacerPlate = add_reinf(spacerPlate, config, kp,
                            shp, config.spacerThickness)
    spacerPlate = spacerPlate.faces(">Z").workplane().pushPoints(
        shp).hole(config.screwHoleDiameter)

    switchPlate = get_base(config, kp, config.plateThickness).cut(keys)

    topPlate = get_base(config, kp, config.plateThickness, True)
    if config.cnc:
        topPlate = add_reinf(topPlate, config, kp, shp, config.plateThickness)

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

    if config.cnc:
        switchPlate = switchPlate.faces(">Z").workplane().pushPoints(
            shp).hole(config.screwHoleDiameter)
        topPlate = topPlate.faces(">Z").workplane().pushPoints(
            shp).hole(config.screwHoleDiameter - 1)
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
    else:
        topPlate = topPlate.faces(">Z").edges().fillet(0.7)
        bottomPlate = bottomPlate.faces("<Z").edges().fillet(1.0)
        topPlate = spacerPlate\
            .union(switchPlate.translate((0, 0, config.spacerThickness)))\
            .union(topPlate.translate((0, 0, config.spacerThickness + config.plateThickness)))
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

    cq.exporters.export(exp, os.path.join(odir, '{}.stl'.format(config.name)))
    cq.exporters.export(exp, os.path.join(
        odir, '{}.svg'.format(config.name)), opt=opt)

    assy.save(os.path.join(odir, '{}.step'.format(config.name)))
    return assy


for config in configs:
    for cnc in [False, True]:
        for split in [False, True]:
            for shape in [Shape.LEAN, Shape.HULL]:
                config.cnc = cnc
                config.split = split
                config.shape = shape
                config.update_name()

                assy = generate(config)
                # show_object(assy)
