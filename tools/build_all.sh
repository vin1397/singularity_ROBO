#!/usr/bin/env bash
# Full pipeline: generate -> upgrade to native KiCad 10 -> ERC -> netlist check -> exports
set -e
cd "$(dirname "$0")/.."
K="env -i HOME=$HOME PATH=/usr/bin:/bin LANG=C.UTF-8 /usr/bin/kicad-cli"

echo "== 1/5 generate project =="
python3 tools/make_project.py

echo "== 2/5 upgrade to native KiCad 10 schematic format =="
$K sch upgrade --force Singularity_ROBO.kicad_sch

echo "== 3/5 ERC =="
$K sch erc --format report --severity-all -o Singularity_ROBO-ERC.rpt Singularity_ROBO.kicad_sch
cat Singularity_ROBO-ERC.rpt

echo "== 4/5 netlist vs intended connectivity =="
python3 tools/verify_netlist.py

echo "== 5/5 exports =="
$K sch export pdf -o Singularity_ROBO-schematic.pdf Singularity_ROBO.kicad_sch
mkdir -p build
pdftoppm -png -r 150 Singularity_ROBO-schematic.pdf build/page
mv -f build/page-1.png Singularity_ROBO-schematic.png
echo "done"
