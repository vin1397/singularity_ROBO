#!/usr/bin/env python3
"""KiCad s-expression parsing / symbol extraction helpers."""
import re, sys, math

# ---------------------------------------------------------------- s-expr parse
TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+')

class QStr(str):
    """A string that was quoted in the source."""
    pass

def parse(text):
    """Parse s-expression text into nested lists."""
    stack = [[]]
    for m in TOKEN.finditer(text):
        t = m.group(0)
        if t == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
        elif t == ')':
            stack.pop()
        elif t.startswith('"'):
            stack[-1].append(QStr(unquote(t)))
        else:
            stack[-1].append(t)
    return stack[0]

def unquote(t):
    return bytes(t[1:-1], 'utf-8').decode('unicode_escape') if '\\' in t else t[1:-1]

def quote(s):
    s = str(s).replace('\\', '\\\\').replace('"', '\\"')
    s = s.replace('\n', '\\n').replace('\t', '\\t')
    return '"' + s + '"'

def dumps(node, indent=0):
    """Serialize back to KiCad-style indented s-expression."""
    pad = '\t' * indent
    if isinstance(node, list):
        if not node:
            return pad + '()'
        # short form: list of atoms only
        if all(not isinstance(x, list) for x in node):
            return pad + '(' + ' '.join(atom(x) for x in node) + ')'
        head = node[0]
        out = [pad + '(' + (atom(head) if not isinstance(head, list) else dumps(head, 0).lstrip())]
        for child in node[1:]:
            if isinstance(child, list):
                out.append('\n' + dumps(child, indent + 1))
            else:
                out.append(' ' + atom(child))
        out.append('\n' + pad + ')')
        return ''.join(out)
    return pad + atom(node)

def atom(a):
    if isinstance(a, QStr):
        return quote(str(a))
    return str(a)

# ---------------------------------------------------------------- walk helpers
def find_all(node, tag):
    """All direct children lists whose head == tag."""
    return [c for c in node if isinstance(c, list) and c and c[0] == tag]

def find(node, tag):
    r = find_all(node, tag)
    return r[0] if r else None

def prop(sym, name):
    for p in find_all(sym, 'property'):
        if str(p[1]) == name:
            return p
    return None

# ---------------------------------------------------------------- symbol info
class Pin:
    def __init__(self, node, unit):
        self.unit = unit
        self.number = str(find(node, 'number')[1])
        self.name = str(find(node, 'name')[1])
        self.etype = node[1]                      # passive / input / power_in ...
        self.style = node[2]
        at = find(node, 'at')
        self.x = float(at[1]); self.y = float(at[2])
        self.angle = int(float(at[3])) if len(at) > 3 else 0
        self.length = float(find(node, 'length')[1])
    def __repr__(self):
        return f'<pin {self.number} {self.name} {self.etype} @({self.x},{self.y}) a{self.angle}>'

def load_symbol_file(path):
    return parse(open(path, encoding='utf-8').read())[0]

def get_symbol(symfile, name):
    """Return top-level symbol node named `name` from a parsed .kicad_sym file."""
    for s in find_all(symfile, 'symbol'):
        if str(s[1]) == name:
            return s
    raise KeyError(name)

def symbol_pins(sym):
    """Pins of a (possibly multi-unit) symbol node."""
    pins = []
    for sub in find_all(sym, 'symbol'):
        m = re.match(r'.*_(\d+)_(\d+)$', str(sub[1]))
        if not m:
            continue
        unit = int(m.group(1))
        for p in find_all(sub, 'pin'):
            pins.append(Pin(p, unit))
    return pins

def symbol_units(sym):
    return sorted({p.unit for p in symbol_pins(sym)}) or [1]

# ---------------------------------------------------------------- transforms
# KiCad maps a library point (x, y) [y up] into schematic offset for a symbol
# placed at (sx, sy) with rotation `rot` (0/90/180/270 CW-as-drawn?) and
# optional mirror.  We only support rotation + no-mirror here; the mapping is
# validated against real template schematics by tools/validate_transform.py.
#
#   rot 0   : ( x, -y)
#   rot 90  : ( y,  x)   -> drawn rotated 90 deg counter-clockwise
#   rot 180 : (-x,  y)
#   rot 270 : (-y, -x)
ROT = {
    0:   lambda x, y: ( x, -y),
    90:  lambda x, y: ( y,  x),
    180: lambda x, y: (-x,  y),
    270: lambda x, y: (-y, -x),
}

def pin_abs(pin, sx, sy, rot=0):
    dx, dy = ROT[rot](pin.x, pin.y)
    return (round(sx + dx, 4), round(sy + dy, 4))
