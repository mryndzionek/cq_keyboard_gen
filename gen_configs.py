import json
from enum import IntEnum
from typing import Optional, Tuple
import math


class Shape(IntEnum):
    LEAN = 0
    HULL = 1


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
    mcu_footprint = Optional[Tuple[float, float]]

    def __init__(self, nc, nr, cs=19, rs=19, switchHoleSize=13.97,
                 angle=10, hOffset=None, plateThickness=1.5,
                 spacerThickness=8.0, screwHoleDiameter=3.0,
                 shape=Shape.LEAN, split=False,
                 staggering=[0, 5, 11, 6, 3],
                 thumbKeys=None,
                 cnc=False,
                 notched=True,
                 mcu_footprint=(30, 60)
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
        self.mcu_footprint = mcu_footprint

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

    Config(5, 5, hOffset=70, thumbKeys=[
           (-1, 1), (-1, 0), (-2, 1), (-2, 0)],
           staggering=[-12, -3, 0, 5, 11, 6, 3]),

    Config(5, 6, hOffset=65, thumbKeys=[
           (-1, 1), (-1, 0), (-2, 1), (-2, 0), (0, -1)],
           staggering=[10, 15, 0, 5, 11, 6, 3]),

    # my favourite configs
    Config(6, 3, hOffset=50, angle=18.5,
           staggering=[8, 0, 5, 11, 6, 3, 2],
           thumbKeys=[(-1, -1), (0, -1), (-1, -2), (1, -1)]),
           
    Config(6, 4, angle=18.5,
           staggering=[0, 5, 11, 6, 3, 2]),

    Config(6, 4, angle=18.5,
           staggering=[0, 0, 5, 11, 6, 3, 2],
           thumbKeys=[(-1, 0), (1, -1)]),

    # # some bigger edge case :)
    Config(10, 10, angle=18.5,
           staggering=[0, 0, 5, 11, 6, 3, 2],
           thumbKeys=[(0, -1), (-1, 0)])
]

if __name__ == "__main__":
    for config in configs:
        for cnc in [False, True]:
            for split in [False, True]:
                for shape in [Shape.LEAN]:
                    config.cnc = cnc
                    config.split = split
                    config.shape = shape
                    config.update_name()

                    with open("configs/" + config.name + ".json", 'w', encoding='utf-8') as f:
                        json.dump(config.__dict__, f)
