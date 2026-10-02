#!/usr/bin/env python3
"""
Generate the complete SINGULARITY ROBO KiCad project:
  Singularity_ROBO.kicad_sch  - real schematic (symbols, pins, wires, junctions,
                                power symbols, net labels, no-connects)
  Singularity_ROBO.kicad_pro  - project file
  Singularity_ROBO.kicad_sym  - project symbol library (+11V_MOTOR, +5V_SERVO)
  sym-lib-table               - project library table
plus build/expected_nets.json used by verify_netlist.py.

All geometry is on the 1.27 mm (50 mil) grid; pin positions are computed from
the real library symbol definitions, never hand-typed.
"""
import os, sys, json, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kisym import (parse, dumps, QStr, find, find_all,
                   load_symbol_file, get_symbol, symbol_pins)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMDIR = '/usr/share/kicad/symbols'
PROJ = 'Singularity_ROBO'
GRID = 1.27
NS = uuid.UUID('6f9619ff-8b86-d011-b42d-00cf4fc964ff')
ROOT_UUID = str(uuid.uuid5(NS, PROJ + '|root-sheet'))

def uid(*a):
    return str(uuid.uuid5(NS, PROJ + '|' + '|'.join(str(x) for x in a)))

def esc(s):
    """Escape a string for use inside a KiCad quoted token."""
    return (str(s).replace('\\', '\\\\').replace('"', '\\"')
            .replace('\n', '\\n').replace('\t', '\\t'))

def chk(v, what=''):
    r = round(v / GRID) * GRID
    assert abs(r - v) < 1e-6, f'off-grid coordinate {v} ({what})'
    return round(v, 4)

# ------------------------------------------------------------------ libraries
_LIBCACHE = {}
def lib_symbol(lib, name):
    if lib not in _LIBCACHE:
        _LIBCACHE[lib] = load_symbol_file(f'{SYMDIR}/{lib}.kicad_sym')
    sym = parse(dumps(get_symbol(_LIBCACHE[lib], name)))[0]   # deep copy
    sym[1] = QStr(f'{lib}:{name}')
    return sym

def project_power_symbol(name):
    """Custom power symbol derived from power:+5V."""
    base = load_symbol_file(f'{SYMDIR}/power.kicad_sym')
    sym = parse(dumps(get_symbol(base, '+5V')))[0]
    old = str(sym[1])
    sym[1] = QStr(name)
    # rename unit sub-symbols (Parent_0_1 style) to match the new parent
    for sub in find_all(sym, 'symbol'):
        s = str(sub[1])
        if s.startswith(old + '_'):
            sub[1] = QStr(name + s[len(old):])
    for p in find_all(sym, 'property'):
        if str(p[1]) == 'Value':
            p[2] = QStr(name)
        if str(p[1]) == 'Description':
            p[2] = QStr(f'Power symbol creates a global label with name "{name}"')
    return sym

# symbol definitions we embed: (lib, name)
USED_LIBSYMS = [
    ('Device', 'Battery_Cell'),
    ('Device', 'R'),
    ('Motor', 'Motor_DC'),
    ('Driver_Motor', 'L298HN'),
    ('Driver_LED', 'PCA9685PW'),
    ('Connector', 'Raspberry_Pi_2_3'),
    ('Connector_Generic', 'Conn_02x08_Odd_Even'),
    ('Connector_Generic', 'Conn_01x12'),
    ('Connector_Generic', 'Conn_01x14'),
    ('Connector_Generic', 'Conn_01x04'),
    ('Connector_Generic', 'Conn_01x03'),
    ('Connector_Generic', 'Conn_01x02'),
    ('power', 'GND'),
    ('power', '+5V'),
    ('power', 'PWR_FLAG'),
]
PROJECT_SYM = '+11V_MOTOR, +5V_SERVO'

# ------------------------------------------------------------------ schematic
class Sch:
    def __init__(self):
        self.libsyms = []        # embedded lib symbol nodes
        self.placed = {}         # ref -> dict(lib_id, x, y, pins, ...)
        self.wires = []          # list of (list of (x,y)) polylines
        self.labels = []         # (name, x, y, side)
        self.ncs = []            # (x, y)
        self.texts = []          # (text, x, y, size, bold)
        self.pwrs = []           # (kind, x, y, ref, value_pos)
        self.flags = []          # (x, y, ref, value_pos)
        self.junctions = []      # computed
        self.explicit_junctions = set()
        self.expected = {}       # net name -> set((ref,pin))
        self.wire_groups = []    # list[set((ref,pin))] for unnamed direct wires
        self.nc_pins = set()     # (ref,pin)
        self.pwr_n = 0
        self.flg_n = 0
        for lib, name in USED_LIBSYMS:
            self.libsyms.append(lib_symbol(lib, name))
        for pname in ('+11V_MOTOR', '+5V_SERVO'):
            sym = project_power_symbol(pname)
            sym[1] = f'{PROJ}:{pname}'     # lib_symbols keys need Lib:Name
            self.libsyms.append(sym)

    # ---------------------------------------------------------- placement
    def place(self, lib_id, ref, value, x, y, ref_at, val_at, value_size=1.27):
        lib, name = lib_id.split(':')
        pins = {p.number: p for p in
                symbol_pins(get_symbol(load_symbol_file(f'{SYMDIR}/{lib}.kicad_sym'), name))}
        self.placed[ref] = dict(lib_id=lib_id, x=chk(x, ref), y=chk(y, ref),
                                value=value, pins=pins,
                                ref_at=(round(ref_at[0], 4), round(ref_at[1], 4)),
                                val_at=(round(val_at[0], 4), round(val_at[1], 4)),
                                value_size=value_size)
        return ref

    def pin(self, ref, num):
        s = self.placed[ref]
        p = s['pins'][num]
        return (round(s['x'] + p.x, 4), round(s['y'] - p.y, 4))

    def dirv(self, ref, num):
        """unit vector pointing AWAY from the body (stub direction)"""
        a = s_angle = self.placed[ref]['pins'][num].angle
        # body direction in schematic coords:
        bx = {0: 1, 180: -1, 90: 0, 270: 0}[a]
        by = {0: 0, 180: 0, 90: -1, 270: 1}[a]
        return (-bx, -by)

    # ---------------------------------------------------------- connections
    def wire(self, *pts):
        """Store an orthogonal run as individual 2-point segments."""
        pts = [(chk(x, 'wire'), chk(y, 'wire')) for x, y in pts]
        for a, b in zip(pts, pts[1:]):
            assert a != b, f'zero-length wire at {a}'
            if a[0] != b[0] and a[1] != b[1]:
                raise AssertionError(f'non-orthogonal segment {a}->{b}')
            self.wires.append((a, b))
        return pts[-1]

    def conn(self, ref, num, pts=None, L=7.62):
        """wire from pin through optional extra points; returns end point"""
        start = self.pin(ref, num)
        if pts is None:
            d = self.dirv(ref, num)
            end = (round(start[0] + d[0] * L, 4), round(start[1] + d[1] * L, 4))
            pts = [end]
        end = pts[-1]
        self.wire(start, *pts)
        return end

    def label(self, name, x, y, side='left'):
        self.labels.append((name, chk(x, 'label'), chk(y, 'label'), side))

    def conn_label(self, ref, num, name, L=7.62, extra=None):
        end = self.conn(ref, num, extra, L)
        side = 'right' if self.dirv(ref, num)[0] < 0 else 'left'
        # stub going left -> text extends left (justify right) and vice versa
        self.label(name, end[0], end[1], side)
        self.expected.setdefault(name, set()).add((ref, num))
        return end

    def pwr(self, kind, x, y, ref_at=None, val_at=None):
        self.pwr_n += 1
        ref = f'#PWR{self.pwr_n:02d}'
        x, y = chk(x, 'pwr'), chk(y, 'pwr')
        if kind == 'GND':
            ref_at = ref_at or (x, y + 3.81)
            val_at = val_at or (x + 0.11, y + 4.318)
        else:
            ref_at = ref_at or (x, y - 3.81)
            val_at = val_at or (x + 0.38, y - 4.318)
        self.pwrs.append(dict(kind=kind, x=x, y=y, ref=ref,
                              ref_at=(round(ref_at[0], 4), round(ref_at[1], 4)),
                              val_at=(round(val_at[0], 4), round(val_at[1], 4))))
        return (x, y)

    def conn_pwr(self, ref, num, kind, L=7.62, bend=None, val_at=None):
        """stub pin -> optional bends -> power symbol."""
        start = self.pin(ref, num)
        d = self.dirv(ref, num)
        ex, ey = round(start[0] + d[0] * L, 4), round(start[1] + d[1] * L, 4)
        pts = [(ex, ey)]
        if bend == 'up':
            pts.append((ex, round(ey - 5.08, 4)))
        elif bend == 'down':
            pts.append((ex, round(ey + 5.08, 4)))
        elif isinstance(bend, list):
            pts.extend(bend)
        self.wire(start, *pts)
        end = pts[-1]
        self.pwr(kind, end[0], end[1], val_at=val_at)
        self.expected.setdefault(kind, set()).add((ref, num))
        return end

    def conn_gnd(self, ref, num, L=7.62):
        d = self.dirv(ref, num)
        return self.conn_pwr(ref, num, 'GND', L, bend='down' if d[1] >= 0 else None)

    def conn_nc(self, ref, num, via_wire=False):
        if via_wire:
            end = self.conn(ref, num, L=5.08)
            self.ncs.append((chk(end[0]), chk(end[1])))
        else:
            p = self.pin(ref, num)
            self.ncs.append((chk(p[0]), chk(p[1])))
        self.nc_pins.add((ref, num))

    def direct(self, *pairs):
        """wire-only (unnamed) net: pairs of (ref,pin) connected with wires"""
        grp = set()
        for ref, num in pairs:
            grp.add((ref, num))
        self.wire_groups.append(grp)
        return grp

    def text(self, s, x, y, size=1.5, bold=False):
        self.texts.append((s, round(x, 4), round(y, 4), size, bold))

    # ---------------------------------------------------------- junctions
    def compute_junctions(self):
        def on_interior(p, seg):
            (x1, y1), (x2, y2) = seg
            if x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2):
                return True
            if y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2):
                return True
            return False
        ends = {}
        for i, seg in enumerate(self.wires):
            for p in seg:
                ends.setdefault(p, set()).add(i)
        for p, ws in ends.items():
            n_int = sum(1 for i, seg in enumerate(self.wires)
                        if i not in ws and on_interior(p, seg))
            if len(ws) >= 3 or (len(ws) >= 1 and n_int >= 1) or n_int >= 2:
                self.junctions.append(p)
        for pw in self.pwrs + [dict(x=f['x'], y=f['y']) for f in self.flags]:
            p = (pw['x'], pw['y'])
            if any(on_interior(p, seg) for seg in self.wires):
                self.junctions.append(p)
        self.junctions = sorted(set(self.junctions) | self.explicit_junctions)

    # ---------------------------------------------------------- emit
    def emit(self):
        L = []
        A = L.append
        A('(kicad_sch')
        A('\t(version 20250114)')
        A('\t(generator "eeschema")')
        A('\t(generator_version "9.0")')
        A(f'\t(uuid "{ROOT_UUID}")')
        A('\t(paper "A2")')
        A('\t(title_block')
        A('\t\t(title "SINGULARITY ROBO - Main Electrical Schematic")')
        A('\t\t(date "2026-10-03")')
        A('\t\t(rev "1.0")')
        A('\t\t(company "SINGULARITY ROBO")')
        A('\t\t(comment 1 "3-wheel robot: 2 driven wheels + caster | Raspberry Pi 3 Model B+ (Gemini AI) | ESP32-CAM person detection")')
        A('\t\t(comment 2 "3S LiPo 11.1V 2200mAh 80C -> LM2596S-ADJ logic +5V | dedicated +5V_SERVO rail | L298N motor bridge")')
        A('\t\t(comment 3 "PCA9685 16ch I2C PWM | 4x TowerPro MG996R | FlySky FS-i6X / FS-iA10B | HC-SR04 | ILI9341 2.4in SPI TFT")')
        A('\t\t(comment 4 "Generated for KiCad 10.x | common ground, motor / logic / servo rails separated")')
        A('\t)')
        # ---- lib symbols
        A('\t(lib_symbols')
        for s in self.libsyms:
            for ln in dumps(s, 1).split('\n'):
                A(ln)
        A('\t)')
        # ---- junctions
        for i, p in enumerate(self.junctions):
            A('\t(junction')
            A(f'\t\t(at {p[0]} {p[1]})')
            A('\t\t(diameter 1.016)')
            A('\t\t(color 0 0 0 0)')
            A(f'\t\t(uuid "{uid("junc", i, p)}")')
            A('\t)')
        # ---- no connects
        for i, p in enumerate(self.ncs):
            A('\t(no_connect')
            A(f'\t\t(at {p[0]} {p[1]})')
            A(f'\t\t(uuid "{uid("nc", i, p)}")')
            A('\t)')
        # ---- wires
        for i, (a, b) in enumerate(self.wires):
            A('\t(wire')
            A('\t\t(pts')
            A(f'\t\t\t(xy {a[0]} {a[1]}) (xy {b[0]} {b[1]})')
            A('\t\t)')
            A('\t\t(stroke')
            A('\t\t\t(width 0)')
            A('\t\t\t(type solid)')
            A('\t\t)')
            A(f'\t\t(uuid "{uid("wire", i, a, b)}")')
            A('\t)')
        # ---- labels
        for i, (name, x, y, side) in enumerate(self.labels):
            A(f'\t(label "{esc(name)}"')
            A(f'\t\t(at {x} {y} 0)')
            A('\t\t(effects')
            A('\t\t\t(font')
            A('\t\t\t\t(size 1.27 1.27)')
            A('\t\t\t)')
            A(f'\t\t\t(justify {side} bottom)')
            A('\t\t)')
            A(f'\t\t(uuid "{uid("label", i, name, x, y)}")')
            A('\t)')
        # ---- free text
        for i, (s, x, y, size, bold) in enumerate(self.texts):
            A(f'\t(text "{esc(s)}"')
            A('\t\t(exclude_from_sim no)')
            A(f'\t\t(at {x} {y} 0)')
            A('\t\t(effects')
            A('\t\t\t(font')
            A(f'\t\t\t\t(size {size} {size})')
            if bold:
                A('\t\t\t\t(bold yes)')
            A('\t\t\t)')
            A('\t\t\t(justify left top)')
            A('\t\t)')
            A(f'\t\t(uuid "{uid("text", i, x, y)}")')
            A('\t)')
        # ---- placed symbols
        for ref, s in sorted(self.placed.items()):
            self._emit_symbol(A, ref, s)
        for pw in self.pwrs:
            self._emit_power(A, pw)
        for i, fl in enumerate(self.flags):
            self._emit_flag(A, i, fl)
        # ---- sheet instances
        A('\t(sheet_instances')
        A('\t\t(path "/"')
        A('\t\t\t(page "1")')
        A('\t\t)')
        A('\t)')
        A('\t(embedded_fonts no)')
        A(')')
        return '\n'.join(L) + '\n'

    def _props(self, A, ref, s, hidden_ref=False):
        A(f'\t\t(property "Reference" "{ref}"')
        A(f'\t\t\t(at {s["ref_at"][0]} {s["ref_at"][1]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        if hidden_ref:
            A('\t\t\t\t(hide yes)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        A(f'\t\t(property "Value" "{esc(s["value"])}"')
        A(f'\t\t\t(at {s["val_at"][0]} {s["val_at"][1]} {s.get("val_angle", 0)})')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A(f'\t\t\t\t\t(size {s.get("value_size", 1.27)} {s.get("value_size", 1.27)})')
        A('\t\t\t\t)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        for pname, pval in (('Footprint', ''), ('Datasheet', ''), ('Description', '')):
            A(f'\t\t(property "{pname}" "{pval}"')
            A(f'\t\t\t(at {s["x"]} {s["y"]} 0)')
            A('\t\t\t(effects')
            A('\t\t\t\t(font')
            A('\t\t\t\t\t(size 1.27 1.27)')
            A('\t\t\t\t)')
            A('\t\t\t\t(hide yes)')
            A('\t\t\t)')
            A('\t\t)')

    def _emit_symbol(self, A, ref, s):
        A('\t(symbol')
        A(f'\t\t(lib_id "{s["lib_id"]}")')
        A(f'\t\t(at {s["x"]} {s["y"]} 0)')
        A('\t\t(unit 1)')
        A('\t\t(exclude_from_sim no)')
        A('\t\t(in_bom yes)')
        A('\t\t(on_board yes)')
        A('\t\t(dnp no)')
        A(f'\t\t(uuid "{uid("sym", ref)}")')
        self._props(A, ref, s)
        for num in s['pins']:
            A(f'\t\t(pin "{num}"')
            A(f'\t\t\t(uuid "{uid("pin", ref, num)}")')
            A('\t\t)')
        A('\t\t(instances')
        A(f'\t\t\t(project "{PROJ}"')
        A(f'\t\t\t\t(path "/{ROOT_UUID}"')
        A(f'\t\t\t\t\t(reference "{ref}")')
        A('\t\t\t\t\t(unit 1)')
        A('\t\t\t\t)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t)')

    def _emit_power(self, A, pw):
        lib_id = ('Singularity_ROBO:' if pw['kind'] in ('+11V_MOTOR', '+5V_SERVO')
                  else 'power:') + pw['kind']
        A('\t(symbol')
        A(f'\t\t(lib_id "{lib_id}")')
        A(f'\t\t(at {pw["x"]} {pw["y"]} 0)')
        A('\t\t(unit 1)')
        A('\t\t(exclude_from_sim no)')
        A('\t\t(in_bom yes)')
        A('\t\t(on_board yes)')
        A('\t\t(dnp no)')
        A(f'\t\t(uuid "{uid("pwr", pw["ref"])}")')
        A(f'\t\t(property "Reference" "{pw["ref"]}"')
        A(f'\t\t\t(at {pw["ref_at"][0]} {pw["ref_at"][1]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(hide yes)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        A(f'\t\t(property "Value" "{esc(pw["kind"])}"')
        A(f'\t\t\t(at {pw["val_at"][0]} {pw["val_at"][1]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t\t(property "Footprint" ""')
        A(f'\t\t\t(at {pw["x"]} {pw["y"]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(hide yes)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t\t(property "Datasheet" ""')
        A(f'\t\t\t(at {pw["x"]} {pw["y"]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(hide yes)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t\t(property "Description" ""')
        A(f'\t\t\t(at {pw["x"]} {pw["y"]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(hide yes)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t\t(pin "1"')
        A(f'\t\t\t(uuid "{uid("pwrpin", pw["ref"])}")')
        A('\t\t)')
        A('\t\t(instances')
        A(f'\t\t\t(project "{PROJ}"')
        A(f'\t\t\t\t(path "/{ROOT_UUID}"')
        A(f'\t\t\t\t\t(reference "{pw["ref"]}")')
        A('\t\t\t\t\t(unit 1)')
        A('\t\t\t\t)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t)')

    def _emit_flag(self, A, i, fl):
        x, y, ref = fl['x'], fl['y'], fl['ref']
        A('\t(symbol')
        A('\t\t(lib_id "power:PWR_FLAG")')
        A(f'\t\t(at {x} {y} 0)')
        A('\t\t(unit 1)')
        A('\t\t(exclude_from_sim no)')
        A('\t\t(in_bom yes)')
        A('\t\t(on_board yes)')
        A('\t\t(dnp no)')
        A(f'\t\t(uuid "{uid("flag", ref)}")')
        A(f'\t\t(property "Reference" "{ref}"')
        A(f'\t\t\t(at {x} {y - 3.81} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(hide yes)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t\t(property "Value" "PWR_FLAG"')
        A(f'\t\t\t(at {fl["val_at"][0]} {fl["val_at"][1]} 0)')
        A('\t\t\t(effects')
        A('\t\t\t\t(font')
        A('\t\t\t\t\t(size 1.27 1.27)')
        A('\t\t\t\t)')
        A('\t\t\t\t(justify left bottom)')
        A('\t\t\t)')
        A('\t\t)')
        for pname in ('Footprint', 'Datasheet', 'Description'):
            A(f'\t\t(property "{pname}" ""')
            A(f'\t\t\t(at {x} {y} 0)')
            A('\t\t\t(effects')
            A('\t\t\t\t(font')
            A('\t\t\t\t\t(size 1.27 1.27)')
            A('\t\t\t\t)')
            A('\t\t\t\t(hide yes)')
            A('\t\t\t)')
            A('\t\t)')
        A('\t\t(pin "1"')
        A(f'\t\t\t(uuid "{uid("flagpin", ref)}")')
        A('\t\t)')
        A('\t\t(instances')
        A(f'\t\t\t(project "{PROJ}"')
        A(f'\t\t\t\t(path "/{ROOT_UUID}"')
        A(f'\t\t\t\t\t(reference "{ref}")')
        A('\t\t\t\t\t(unit 1)')
        A('\t\t\t\t)')
        A('\t\t\t)')
        A('\t\t)')
        A('\t)')

    def flag(self, x, y, val_at=None):
        self.flg_n += 1
        ref = f'#FLG{self.flg_n:02d}'
        val_at = val_at or (x + 0.38, y - 4.318)
        self.flags.append(dict(x=chk(x), y=chk(y), ref=ref,
                               val_at=(round(val_at[0], 4), round(val_at[1], 4))))
        return ref
