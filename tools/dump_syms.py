#!/usr/bin/env python3
"""Dump pin info for the symbols we plan to use."""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from kisym import *

SYMDIR = '/usr/share/kicad/symbols'

WANT = [
    ('Connector', 'Raspberry_Pi_2_3'),
    ('Driver_Motor', 'L298HN'),
    ('Driver_LED', 'PCA9685PW'),
    ('Regulator_Switching', 'LM2596S-ADJ'),
    ('Motor', 'Motor_DC'),
    ('Device', 'Battery_Cell'),
    ('Device', 'R'),
    ('power', 'GND'),
    ('power', '+5V'),
    ('power', 'PWR_FLAG'),
    ('Connector_Generic', 'Conn_02x08_Odd_Even'),
    ('Connector_Generic', 'Conn_02x20_Odd_Even'),
    ('Connector_Generic', 'Conn_01x03'),
    ('Connector_Generic', 'Conn_01x04'),
    ('Connector_Generic', 'Conn_01x12'),
    ('Connector_Generic', 'Conn_01x14'),
    ('Connector_Generic', 'Conn_01x16'),
]

cache = {}
for lib, name in WANT:
    if lib not in cache:
        cache[lib] = load_symbol_file(f'{SYMDIR}/{lib}.kicad_sym')
    try:
        sym = get_symbol(cache[lib], name)
    except KeyError:
        print(f'### {lib}:{name}  -- NOT FOUND')
        continue
    pins = symbol_pins(sym)
    print(f'### {lib}:{name}   pins={len(pins)}  units={symbol_units(sym)}')
    for p in sorted(pins, key=lambda p: (p.unit, len(p.number), p.number)):
        print(f'   unit{p.unit}  pin {p.number:>3}  {p.name:<18} {p.etype:<14} at=({p.x},{p.y}) ang={p.angle} len={p.length}')
    # bounding box of graphics
    xs, ys = [], []
    for g in sym:
        if isinstance(g, list) and g and g[0] in ('rectangle', 'polyline', 'circle', 'arc'):
            for xy in find_all(g, 'pts') :
                pass
    print()
