#!/usr/bin/env python3
"""Verify the KiCad netlist against the intended connectivity (build/expected_nets.json)."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kisym import parse, find, find_all, QStr

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def run_netlist():
    out = os.path.join(ROOT, 'build', 'actual.net')
    r = subprocess.run(['env', '-i', 'HOME=/home/vin', 'PATH=/usr/bin:/bin',
                        'LANG=C.UTF-8', '/usr/bin/kicad-cli', 'sch', 'export',
                        'netlist', '--format', 'kicadsexpr', '-o', out,
                        os.path.join(ROOT, 'Singularity_ROBO.kicad_sch')],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('netlist export FAILED:', r.stderr)
        sys.exit(1)
    return out

def load_actual(path):
    tree = parse(open(path, encoding='utf-8').read())[0]
    nets = {}
    nets_node = find(tree, 'nets')
    for net in find_all(nets_node, 'net'):
        name = str(find(net, 'name')[1])
        pins = set()
        for node in find_all(net, 'node'):
            ref = str(find(node, 'ref')[1])
            pin = str(find(node, 'pin')[1])
            pins.add((ref, pin))
        nets[name] = pins
    return nets

def main():
    exp = json.load(open(os.path.join(ROOT, 'build', 'expected_nets.json')))
    actual = load_actual(run_netlist())

    # expected partition: named nets + unnamed groups (membership only)
    exp_named = {k: set(map(tuple, v)) for k, v in exp['named'].items()}
    exp_groups = [set(map(tuple, g)) for g in exp['unnamed']]
    exp_nc = set(map(tuple, exp['nc']))

    problems = []

    # local labels are exported with a leading sheet path '/NAME'
    actual_norm = {}
    for n, p in actual.items():
        key = n[1:] if n.startswith('/') else n
        if key in actual_norm:
            problems.append(f'DUPLICATE normalized name "{key}"')
        actual_norm[key] = p

    # separate NC-only 'unconnected-(...)' nets: legitimate for no-connect pins
    nc_nets = {n: p for n, p in actual_norm.items()
               if n.startswith('unconnected-(') and p <= exp_nc}
    wired = {n: p for n, p in actual_norm.items() if n not in nc_nets}

    # 1. every named net exists with exactly the expected pins
    for name, pins in exp_named.items():
        if name not in wired:
            problems.append(f'MISSING NET "{name}" (expected pins {sorted(pins)})')
            continue
        got = wired[name]
        if got != pins:
            missing = pins - got
            extra = got - pins
            if missing:
                problems.append(f'NET "{name}" missing pins: {sorted(missing)}')
            if extra:
                problems.append(f'NET "{name}" has unexpected pins: {sorted(extra)}')

    # 2. no actual net mixes pins from two different expected named nets
    owner = {}
    for name, pins in exp_named.items():
        for p in pins:
            owner[p] = name
    for aname, apins in wired.items():
        owners = {owner[p] for p in apins if p in owner}
        if len(owners) > 1:
            problems.append(f'SHORT: net "{aname}" merges {sorted(owners)}')

    # 3. unnamed groups present as one net each (any name)
    for g in exp_groups:
        found = [n for n, p in wired.items() if p == g]
        if not found:
            hit = [n for n, p in wired.items() if g <= p]
            problems.append(f'UNNAMED GROUP {sorted(g)} not intact; found in: {hit}')

    # 4. every pin on wired nets is covered by expectations (no stray nets)
    all_exp = set()
    for pins in exp_named.values():
        all_exp |= pins
    for g in exp_groups:
        all_exp |= g
    for aname, apins in wired.items():
        for p in apins:
            if p not in all_exp:
                problems.append(f'STRAY PIN {p} on net "{aname}"')

    # 5. NC pins may only live on 'unconnected-' nets made only of NC pins
    for aname, apins in wired.items():
        for p in apins & exp_nc:
            problems.append(f'NC pin {p} is wired into net "{aname}"')
    for aname, apins in nc_nets.items():
        if len(apins) > 2:
            problems.append(f'NC net "{aname}" has too many pins: {sorted(apins)}')

    # 6. report
    print(f'actual nets: {len(actual)} ({len(nc_nets)} NC-only), '
          f'expected named: {len(exp_named)}, unnamed groups: {len(exp_groups)}, '
          f'NC pins: {len(exp_nc)}')
    if problems:
        print(f'\n{len(problems)} CONNECTIVITY PROBLEMS:')
        for p in problems:
            print('  -', p)
        sys.exit(1)
    print('CONNECTIVITY OK: netlist matches intended design exactly')

if __name__ == '__main__':
    main()
