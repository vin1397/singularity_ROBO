#!/usr/bin/env python3
"""Lay out SINGULARITY ROBO and write the complete KiCad project."""
import os, sys, json, math, uuid
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_schematic import (Sch, uid, ROOT_UUID, PROJ, USED_LIBSYMS,
                             project_power_symbol, dumps, ROOT)
from kisym import QStr

S = Sch()

# ===========================================================================
# SECTION 1 - POWER / BATTERY / REGULATORS          (x 14 .. 104)
# ===========================================================================
S.place('Device:Battery_Cell', 'B1', '3S LiPo 11.1V 2200mAh 80C',
        45.72, 63.5, (55.88, 57.15), (55.88, 60.96))
S.conn_pwr('B1', '1', '+11V_MOTOR', L=10.16)          # battery + -> rail
# split off the rail source marker: +11V_MOTOR tap + PWR_FLAG (junction)
S.wire((45.72, 53.34), (55.88, 53.34))
S.flag(55.88, 53.34)
# battery - : vertical drop with T-branch to PWR_FLAG, ending at GND
S.wire((45.72, 66.04), (45.72, 78.74))
S.wire((45.72, 73.66), (55.88, 73.66))
S.pwr('GND', 45.72, 78.74)
S.flag(55.88, 73.66)
S.expected.setdefault('GND', set()).add(('B1', '2'))

# U5 - logic buck (LM2596S-ADJ module, 5.0 V)
S.place('Connector_Generic:Conn_01x04', 'U5', 'LM2596S-ADJ 5.0V LOGIC',
        91.44, 96.52, (88.9, 87.63), (94, 87.63))
S.conn_pwr('U5', '1', '+11V_MOTOR', L=12.7)                           # IN+
S.conn_pwr('U5', '2', 'GND', L=10.16, bend=[(76.2, 104.14)])          # IN-
S.conn_pwr('U5', '3', '+5V', L=7.62, bend=[(78.74, 91.44)])           # OUT+
S.wire((78.74, 99.06), (66.04, 99.06))            # T off OUT+ to PWR_FLAG
S.flag(66.04, 99.06)
S.conn_pwr('U5', '4', 'GND', L=5.08, bend=[(81.28, 109.22)])          # OUT-

# U6 - dedicated high-current servo buck (5.0 V)
S.place('Connector_Generic:Conn_01x04', 'U6', 'LM2596S-ADJ 5.0V SERVO',
        91.44, 139.7, (88.9, 130.81), (94, 130.81))
S.conn_pwr('U6', '1', '+11V_MOTOR', L=12.7)                           # IN+
S.conn_pwr('U6', '2', 'GND', L=10.16, bend=[(76.2, 147.32)])          # IN-
S.conn_pwr('U6', '3', '+5V_SERVO', L=7.62, bend=[(78.74, 134.62)])    # OUT+
S.wire((78.74, 142.24), (66.04, 142.24))
S.flag(66.04, 142.24)
S.conn_pwr('U6', '4', 'GND', L=5.08, bend=[(81.28, 152.4)])           # OUT-

# ===========================================================================
# SECTION 2 - MOTOR DRIVER L298N + GEARED MOTORS     (x 112 .. 230)
# ===========================================================================
S.place('Driver_Motor:L298HN', 'U2', 'L298N',
        152.4, 91.44, (158.75, 116.84), (158.75, 119.38))
S.conn_pwr('U2', '4', '+11V_MOTOR', L=7.62, bend=[(165.1, 66.04)])    # Vs (motor supply)
S.conn_pwr('U2', '9', '+5V', L=7.62)                                  # Vss (logic supply)
# GND + SENSE_A + SENSE_B tied together (no current-sense resistors)
S.wire((144.78, 109.22), (144.78, 114.3), (152.4, 114.3))
S.wire((147.32, 109.22), (147.32, 114.3))
S.wire((152.4, 109.22), (152.4, 116.84))
S.pwr('GND', 152.4, 116.84)
S.expected.setdefault('GND', set()).update(
    {('U2', '1'), ('U2', '8'), ('U2', '15')})
# logic inputs / PWM enables -> labels to Raspberry Pi GPIOs
S.conn_label('U2', '5', 'MOTOR_IN1')
S.conn_label('U2', '7', 'MOTOR_IN2')
S.conn_label('U2', '10', 'MOTOR_IN3')
S.conn_label('U2', '12', 'MOTOR_IN4')
S.conn_label('U2', '6', 'MOTOR_ENA')
S.conn_label('U2', '11', 'MOTOR_ENB')
# half-bridge outputs -> real wires to the motors
S.place('Motor:Motor_DC', 'M1', '37GM385 12V 300RPM',
        198.12, 83.82, (198.12, 76.2), (198.12, 100.33))
S.place('Motor:Motor_DC', 'M2', '37GM385 12V 300RPM',
        215.9, 118.11, (215.9, 110.49), (215.9, 130.81))
S.wire(S.pin('U2', '2'), (190.5, 86.36), (190.5, 78.74), S.pin('M1', '1'))
S.wire(S.pin('U2', '3'), (193.04, 88.9), (193.04, 91.44), S.pin('M1', '2'))
S.wire(S.pin('U2', '13'), (210.82, 93.98), (210.82, 113.03), S.pin('M2', '1'))
S.wire(S.pin('U2', '14'), (208.28, 96.52), (208.28, 125.73), S.pin('M2', '2'))
S.direct(('U2', '2'), ('M1', '1'))
S.direct(('U2', '3'), ('M1', '2'))
S.direct(('U2', '13'), ('M2', '1'))
S.direct(('U2', '14'), ('M2', '2'))

# ===========================================================================
# SECTION 3 - RASPBERRY PI 3 MODEL B+               (x 240 .. 345)
# ===========================================================================
S.place('Connector:Raspberry_Pi_2_3', 'U1', 'Raspberry Pi 3 Model B+',
        279.4, 114.3, (285, 68.58), (240, 165.1))
# power pins (stacked pins share one connection point)
S.conn_pwr('U1', '2', '+5V', L=7.62)                 # 5V pins 2 & 4
S.expected['+5V'].add(('U1', '4'))
S.conn('U1', '1', [(284.48, 76.2)])                  # 3V3 pins 1 & 17 -> NC
S.ncs.append((284.48, 76.2))
S.nc_pins.update({('U1', '1'), ('U1', '17')})
S.conn_pwr('U1', '6', 'GND', L=7.62)                 # 8 stacked GND pins
for n in ('9', '14', '20', '25', '30', '34', '39'):
    S.expected['GND'].add(('U1', n))
# ID EEPROM pins unused
S.conn_nc('U1', '27')
S.conn_nc('U1', '28')

# left-hand GPIOs (labels run west toward motor / sensor / radio blocks)
PI_LEFT = [
    ('8',  'ESP32_RX'),        # GPIO14/TXD  -> ESP32-CAM RX
    ('10', 'ESP32_TX'),        # GPIO15/RXD  <- ESP32-CAM TX
    ('36', 'TFT_RST'),         # GPIO16
    ('11', 'SONAR_TRIG'),      # GPIO17
    ('12', 'MOTOR_ENA'),       # GPIO18/PWM0
    ('35', 'RX_CH4'),          # GPIO19
    ('15', 'MOTOR_IN1'),       # GPIO22
    ('16', 'MOTOR_IN2'),       # GPIO23
    ('18', 'MOTOR_IN3'),       # GPIO24
    ('22', 'MOTOR_IN4'),       # GPIO25
    ('37', 'NAMASTE_SWITCH'),  # GPIO26
    ('38', 'TFT_BL'),          # GPIO20
    ('40', 'TFT_T_IRQ'),       # GPIO21
    ('13', 'ECHO_3V3'),        # GPIO27 <- HC-SR04 divider midpoint
]
for num, net in PI_LEFT:
    S.conn_label('U1', num, net)

# right-hand GPIOs (labels run east toward PCA9685 / TFT)
PI_RIGHT = [
    ('3',  'I2C_SDA'),    # GPIO2  -> PCA9685 SDA
    ('5',  'I2C_SCL'),    # GPIO3  -> PCA9685 SCL
    ('7',  'TFT_DC'),     # GPIO4
    ('29', 'RX_CH1'),     # GPIO5
    ('31', 'RX_CH2'),     # GPIO6
    ('26', 'TFT_T_CS'),   # GPIO7  /CE1 -> touch chip select
    ('24', 'TFT_CS'),     # GPIO8  /CE0 -> display chip select
    ('21', 'TFT_MISO'),   # GPIO9
    ('19', 'TFT_MOSI'),   # GPIO10
    ('23', 'TFT_SCLK'),   # GPIO11
    ('32', 'RX_CH3'),     # GPIO12
    ('33', 'MOTOR_ENB'),  # GPIO13/PWM1
]
for num, net in PI_RIGHT:
    S.conn_label('U1', num, net)

# ===========================================================================
# SECTION 4 - PCA9685 16-CH I2C PWM DRIVER          (x 360 .. 455)
# ===========================================================================
S.place('Driver_LED:PCA9685PW', 'U3', 'PCA9685PW',
        401.32, 111.76, (407.67, 76.2), (407.67, 78.74))
S.conn_pwr('U3', '28', '+5V', L=7.62)                       # VDD logic
S.conn_pwr('U3', '14', 'GND', L=7.62)                       # VSS
S.conn_label('U3', '27', 'I2C_SDA')
S.conn_label('U3', '26', 'I2C_SCL')
S.conn_nc('U3', '25')                                       # EXTCLK unused
S.conn_pwr('U3', '23', 'GND', L=7.62, bend=[(375.92, 106.68)])   # ~OE = enabled
# address inputs A0-A5 all to GND (I2C address 0x40) via a rail with junctions
for n in ('1', '2', '3', '4', '5', '24'):
    S.conn('U3', n, [(373.38, S.pin('U3', n)[1])])
    S.expected.setdefault('GND', set()).add(('U3', n))
S.wire((373.38, 116.84), (373.38, 134.62))
S.pwr('GND', 373.38, 134.62)
# PWM outputs 0-3 -> servo signals
for i, n in enumerate(('6', '7', '8', '9')):
    S.conn_label('U3', n, f'SERVO_CH{i}', L=12.7)
for n in ('10', '11', '12', '13', '15', '16', '17', '18', '19', '20', '21', '22'):
    S.conn_nc('U3', n)                                     # unused channels

# ===========================================================================
# SECTION 5 - MG996R SERVOS + +5V_SERVO RAIL        (x 470 .. 575)
# ===========================================================================
RAIL = 487.68
SERVOS = [
    ('J4', 66.04,  0, 'SERVO1  LEFT ARM'),
    ('J5', 99.06,  1, 'SERVO2  RIGHT ARM'),
    ('J6', 132.08, 2, 'SERVO3  HEAD 1'),
    ('J7', 165.1,  3, 'SERVO4  HEAD 2'),
]
for ref, oy, ch, name in SERVOS:
    S.place('Connector_Generic:Conn_01x03', ref, 'TowerPro MG996R',
            530.86, oy, (535, oy - 7.62), (524, oy + 5.08))
    S.conn_label(ref, '1', f'SERVO_CH{ch}', L=5.08)          # SIGNAL
    S.wire(S.pin(ref, '2'), (RAIL, oy))                      # +5V_SERVO tap
    S.expected.setdefault('+5V_SERVO', set()).add((ref, '2'))
    S.wire(S.pin(ref, '3'), (515.62, oy + 2.54), (515.62, oy + 7.62))
    S.pwr('GND', 515.62, oy + 7.62)
    S.expected.setdefault('GND', set()).add((ref, '3'))
    S.text(name, 515.62, oy - 12.7, 1.5)
S.wire((RAIL, 66.04), (RAIL, 165.1))                        # servo V+ rail
S.pwr('+5V_SERVO', RAIL, 66.04, val_at=(487.68, 57.15))

# ===========================================================================
# SECTION 6 - HC-SR04 + 5V->3.3V ECHO DIVIDER       (x 112 .. 215, y 210+)
# ===========================================================================
S.place('Connector_Generic:Conn_01x04', 'J3', 'HC-SR04',
        170.18, 238.76, (165, 228.6), (170.18, 248.92))
S.conn_pwr('J3', '1', '+5V', L=7.62, bend=[(157.48, 231.14)])          # VCC
S.conn_label('J3', '2', 'SONAR_TRIG', L=15.24)                          # TRIG
S.wire(S.pin('J3', '3'), (149.86, 241.3))                               # ECHO
S.label('SONAR_ECHO', 149.86, 241.3, 'right')
S.expected.setdefault('SONAR_ECHO', set()).add(('J3', '3'))
S.conn_pwr('J3', '4', 'GND', L=7.62, bend=[(157.48, 248.92)])          # GND
# divider: ECHO --R1-- ECHO_3V3 --R2-- GND
S.place('Device:R', 'R1', '1kΩ', 132.08, 259.08, (137.16, 254.0), (137.16, 256.54))
S.place('Device:R', 'R2', '2kΩ', 132.08, 274.32, (137.16, 269.24), (137.16, 271.78))
S.wire(S.pin('R1', '1'), (132.08, 241.3), (149.86, 241.3))
S.expected['SONAR_ECHO'].add(('R1', '1'))
S.wire(S.pin('R1', '2'), S.pin('R2', '1'))
S.label('ECHO_3V3', 132.08, 266.7, 'left')
S.expected.setdefault('ECHO_3V3', set()).update({('R1', '2'), ('R2', '1')})
S.expected['ECHO_3V3'].add(('U1', '13'))
S.conn_pwr('R2', '2', 'GND', L=7.62)

# ===========================================================================
# SECTION 7 - ESP32-CAM VISION MODULE               (x 240 .. 345, y 210+)
# ===========================================================================
S.place('Connector_Generic:Conn_02x08_Odd_Even', 'U4', 'ESP32-CAM',
        289.56, 248.92, (289.56, 233.68), (289.56, 264.16))
S.conn_pwr('U4', '1', '+5V', L=7.62, bend=[(276.86, 236.22)])     # 5V
S.conn_label('U4', '3', 'ESP32_TX', L=10.16)                       # U0T -> Pi RX
S.conn_label('U4', '5', 'ESP32_RX', L=10.16)                       # U0R <- Pi TX
S.conn_pwr('U4', '7', 'GND', L=5.08, bend=[(279.4, 254)])          # GND
S.wire(S.pin('U4', '6'), (304.8, 246.38), (304.8, 248.92))
S.wire(S.pin('U4', '8'), (304.8, 248.92))
S.wire((304.8, 248.92), (304.8, 254))
S.pwr('GND', 304.8, 254)
S.expected.setdefault('GND', set()).update({('U4', '6'), ('U4', '8')})
for n in ('2', '4', '9', '10', '11', '12', '13', '14', '15', '16'):
    S.conn_nc('U4', n)

# ===========================================================================
# SECTION 8 - ILI9341 2.4in SPI TFT + XPT2046 TOUCH (x 360 .. 455, y 195+)
# ===========================================================================
S.place('Connector_Generic:Conn_01x14', 'J2', 'ILI9341 2.4in TFT',
        401.32, 254, (398, 233.68), (401.32, 276.86))
S.conn_pwr('J2', '1', '+5V', L=7.62, bend=[(388.62, 233.68)])     # VCC
S.wire(S.pin('J2', '2'), (370.84, 241.3), (370.84, 250.19))       # GND
S.pwr('GND', 370.84, 250.19)
S.expected.setdefault('GND', set()).add(('J2', '2'))
for num, net in [('3', 'TFT_CS'), ('4', 'TFT_RST'), ('5', 'TFT_DC'),
                 ('6', 'TFT_MOSI'), ('7', 'TFT_SCLK'), ('8', 'TFT_BL'),
                 ('9', 'TFT_MISO'), ('10', 'TFT_SCLK'), ('11', 'TFT_T_CS'),
                 ('12', 'TFT_MOSI'), ('13', 'TFT_MISO'), ('14', 'TFT_T_IRQ')]:
    S.conn_label('J2', num, net)

# ===========================================================================
# SECTION 9 - FLYSKY FS-iA10B RECEIVER              (x 470 .. 575, y 210+)
# ===========================================================================
S.place('Connector_Generic:Conn_01x12', 'J1', 'FlySky FS-iA10B',
        530.86, 248.92, (536, 228.6), (530.86, 269.24))
S.conn_pwr('J1', '1', '+5V', L=7.62, bend=[(518.16, 231.14)])      # VCC
S.wire(S.pin('J1', '2'), (505.46, 238.76), (505.46, 241.3))        # GND
S.pwr('GND', 505.46, 241.3)
S.expected.setdefault('GND', set()).add(('J1', '2'))
for num, net in [('3', 'RX_CH1'), ('4', 'RX_CH2'), ('5', 'RX_CH3'),
                 ('6', 'RX_CH4'), ('7', 'NAMASTE_SWITCH')]:
    S.conn_label('J1', num, net)
for n in ('8', '9', '10', '11', '12'):
    S.conn_nc('J1', n)

# ===========================================================================
# SECTION 10 - DUBSTEP POP 600 BLUETOOTH SPEAKER    (x 470 .. 575, y 285+)
# ===========================================================================
S.place('Connector_Generic:Conn_01x02', 'J8', 'Dubstep Pop 600',
        530.86, 302.26, (526, 293.37), (530.86, 307.34))
S.conn_pwr('J8', '1', '+5V', L=7.62, bend=[(518.16, 297.18)])        # USB power
S.conn_pwr('J8', '2', 'GND', L=7.62, bend=[(518.16, 309.88)])

# ===========================================================================
# TEXT / NOTES
# ===========================================================================
B = lambda s, x, y: S.text(s, x, y, 1.5)
S.text('SINGULARITY ROBO  -  MAIN ELECTRICAL SCHEMATIC', 14, 19.05, 2.5, bold=True)

S.text('1 .  POWER / BATTERY / REGULATORS', 14, 30.48, 1.8, bold=True)
S.text('2 .  MOTOR DRIVER  L298N', 112, 30.48, 1.8, bold=True)
S.text('3 .  RASPBERRY PI 3 MODEL B+  (U1)', 240, 30.48, 1.8, bold=True)
S.text('4 .  PCA9685 16-CH I2C PWM  (U3)', 360, 30.48, 1.8, bold=True)
S.text('5 .  MG996R SERVO INTERFACES', 470, 30.48, 1.8, bold=True)

B("""U5 / U6 = LM2596S-ADJ buck modules
1 IN+   2 IN-   3 OUT+ (5.0V)   4 OUT-""", 60.96, 118.11)
B("""U6 = DEDICATED SERVO BUCK, high current.
Servo rail never loaded by Raspberry Pi.""", 60.96, 162.56)
B("""POWER ARCHITECTURE  -  SINGULARITY ROBO
3S LiPo 11.1V (12.6V max) 2200mAh 80C
A] +11V_MOTOR -> U2 L298N VS   (motors)
B] +11V_MOTOR -> U5 LM2596S-ADJ -> +5V
C] +11V_MOTOR -> U6 LM2596S-ADJ -> +5V_SERVO
   (dedicated high-current servo rail)

+5V feeds: Raspberry Pi, PCA9685 VDD,
HC-SR04, ESP32-CAM, TFT, FlySky RX,
Bluetooth speaker power.

+5V_SERVO feeds: servo V+ rail J4-J7 ONLY.

*** DO NOT CONNECT 11.1V TO RASPBERRY PI ***
U1 5V pins are fed ONLY from U5 +5V.

ALL GROUNDS COMMON: battery - = GND.
Motor 11.1V / logic 5V / servo 5V rails
kept separate; PWR_FLAG marks each source.""", 14, 170.18)

B("""M1 = LEFT wheel, M2 = RIGHT wheel
OUT1/OUT2 = motor A, OUT3/OUT4 = motor B
SENSE_A / SENSE_B tied to GND
(no current-sense resistors fitted).
ENA / ENB = PWM from Pi GPIO18 / GPIO13.
VS = +11V_MOTOR, VSS = +5V logic.""", 112, 139.7)

B("""U1 GPIO MAP (all 26 GPIOs used)
I2C  GPIO2/SDA + GPIO3/SCL -> U3 PCA9685
SPI0 GPIO10/9/11 + CE0/CE1 -> J2 TFT
CE0 = TFT_CS, CE1 = touch T_CS
ENA/ENB = PWM GPIO18 / GPIO13
UART GPIO14/15 <-> U4 ESP32-CAM (crossed)
5V from U5 ONLY - NEVER 11.1V
BT audio -> Dubstep Pop 600 (wireless)""", 240, 175.26)

B("""U3 PCA9685PW:  A0-A5 = GND (addr 0x40),
~OE = GND (outputs enabled), EXTCLK = NC.
VDD = +5V logic.  Servo V+ rail = +5V_SERVO
routed to J4-J7 headers. LED0-3 = CH0-3.""", 360, 160.02)

B("""SERVO POWER RAIL: +5V_SERVO from U6 only.
Header: 1 SIGNAL . 2 +5V_SERVO . 3 GND
(common ground).  NEVER from Pi 5V GPIO.""", 470, 180.34)

S.text('6 .  HC-SR04 ULTRASONIC + ECHO DIVIDER', 112, 213.36, 1.8, bold=True)
S.text('7 .  ESP32-CAM VISION MODULE', 240, 213.36, 1.8, bold=True)
S.text('8 .  ILI9341 2.4in SPI TFT + TOUCH', 360, 213.36, 1.8, bold=True)
S.text('9 .  FLYSKY RC RECEIVER', 470, 213.36, 1.8, bold=True)

B("""ECHO DIVIDER (mandatory level shift)
HC-SR04 ECHO = 5V logic, Pi GPIO = 3.3V
R1 1kO / R2 2kO  ->  ECHO_3V3 = 3.33V
(5V x 2k / 3k).  NEVER wire ECHO direct.""", 145, 290.83)

B("""U0T (GPIO1) = TX -> Pi RXD  = ESP32_TX
U0R (GPIO3) = RX <- Pi TXD  = ESP32_RX
Camera / person detection / inference on Pi
5V from +5V rail, GND common, rest NC.""", 240, 271.78)

B("""J2 = 2.4in ILI9341 240x320 SPI display
with XPT2046 resistive touch.  Touch shares
the SPI bus, T_CS on CE1 (GPIO7).
BL = GPIO20 backlight, VCC = +5V.""", 411.48, 238.76)

B("""FLYSKY FS-i6X  -  WIRELESS TRANSMITTER
(2.4 GHz) binds to J1 FS-iA10B receiver.
CH1-CH4 drive / camera, CH5 = NAMASTE.
Pi reads the PWM channel pulses on GPIO.""", 460, 276.86)

S.text('10 .  BLUETOOTH AUDIO', 470, 296, 1.8, bold=True)
B("""Dubstep Pop 600 speaker: audio link is
BLUETOOTH (wireless) from the Raspberry Pi.
Only +5V / GND are wired (power/charge).""", 470, 316.23)

# ===========================================================================
# FINISH: junctions, lint, emit
# ===========================================================================
S.compute_junctions()

def lint():
    problems = []
    # 1. every non-power pin covered by a wire or no-connect
    wire_pts = set()
    for a, b in S.wires:
        wire_pts.add(a); wire_pts.add(b)
    nc_pts = set(S.ncs)
    for ref, s in S.placed.items():
        for num in s['pins']:
            p = S.pin(ref, num)
            if p in nc_pts:
                continue
            if p in wire_pts:
                continue
            problems.append(f'UNCOVERED PIN {ref}.{num} at {p}')
    # 2. dangling wire ends
    from collections import Counter
    endc = Counter()
    for a, b in S.wires:
        endc[a] += 1; endc[b] += 1
    anchors = set()
    for _, x, y, _ in S.labels:
        anchors.add((x, y))
    for pw in S.pwrs:
        anchors.add((pw['x'], pw['y']))
    for fl in S.flags:
        anchors.add((fl['x'], fl['y']))
    anchors |= nc_pts
    pinpts = {S.pin(r, n) for r, s in S.placed.items() for n in s['pins']}
    for p, c in endc.items():
        if p in anchors or p in pinpts:
            continue
        if c >= 2:
            continue
        # single end not on pin/label/pwr/nc -> interior of another wire?
        interior = False
        for a, b in S.wires:
            (x1, y1), (x2, y2) = a, b
            if x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2):
                interior = True
            if y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2):
                interior = True
        if not interior:
            problems.append(f'DANGLING WIRE END at {p}')
    # 3. labels sit on a wire
    for name, x, y, side in S.labels:
        ok = False
        for a, b in S.wires:
            (x1, y1), (x2, y2) = a, b
            if x1 == x2 == x and min(y1, y2) <= y <= max(y1, y2):
                ok = True
            if y1 == y2 == y and min(x1, x2) <= x <= max(x1, x2):
                ok = True
        if not ok:
            problems.append(f'LABEL NOT ON WIRE: {name} at {(x, y)}')
    # 4. wire crossings without junction / endpoint-on-wire without junction
    junc = set(S.junctions)
    def interior(p, seg):
        (x1, y1), (x2, y2) = seg
        if x1 == x2 == p[0] and min(y1, y2) < p[1] < max(y1, y2):
            return True
        if y1 == y2 == p[1] and min(x1, x2) < p[0] < max(x1, x2):
            return True
        return False
    for i, (a1, b1) in enumerate(S.wires):
        for j, (a2, b2) in enumerate(S.wires):
            if j <= i:
                continue
            # only axis-aligned; compute crossing point
            def orient(p, q, r):
                return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
            pts = []
            for p in (a2, b2):
                if interior(p, (a1, b1)):
                    pts.append(p)
            for p in (a1, b1):
                if interior(p, (a2, b2)):
                    pts.append(p)
            for p in pts:
                if p not in junc:
                    problems.append(f'MISSING JUNCTION at {p} (segments {i},{j})')
    # 5. text overlaps (rough bounding boxes)
    boxes = []
    def add_box(txt, x, y, size, side='left'):
        w = len(txt) * size * 0.72
        if side == 'right':
            x = x - w
        boxes.append((x, y - size, x + w, y, txt[:34]))
    for txt, x, y, size, bold in S.texts:
        lines = txt.split('\n')
        for k, ln in enumerate(lines):
            add_box(ln, x, y + k * size * 1.6, size)
    for name, x, y, side in S.labels:
        add_box(name, x, y, 1.27, side)
    for ref, s in S.placed.items():
        add_box(ref, s['ref_at'][0], s['ref_at'][1], 1.27)
        add_box(s['value'], s['val_at'][0], s['val_at'][1], s['value_size'])
    for pw in S.pwrs:
        add_box(pw['kind'], pw['val_at'][0], pw['val_at'][1], 1.27)
    for fl in S.flags:
        add_box('PWR_FLAG', fl['val_at'][0], fl['val_at'][1], 1.27)
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            ax1, ay1, ax2, ay2, at = boxes[i]
            bx1, by1, bx2, by2, bt = boxes[j]
            if ax1 < bx2 and bx1 < ax2 and ay1 < by2 and by1 < ay2:
                problems.append(f'TEXT OVERLAP: "{at}" vs "{bt}"')
    return problems

probs = lint()
os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)

# --------------------------------------------------------------- schematic
sch_path = os.path.join(ROOT, f'{PROJ}.kicad_sch')
with open(sch_path, 'w', encoding='utf-8') as f:
    f.write(S.emit())

# --------------------------------------------------------------- symbol lib
lib_nodes = [project_power_symbol('+11V_MOTOR'),
             project_power_symbol('+5V_SERVO')]
lib_out = ['(kicad_symbol_lib', '\t(version 20251024)',
           '\t(generator "kicad_symbol_editor")', '\t(generator_version "10.0")']
for n in lib_nodes:
    lib_out.append(dumps(n, 1))
lib_out.append(')')
with open(os.path.join(ROOT, f'{PROJ}.kicad_sym'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(lib_out) + '\n')

# --------------------------------------------------------------- sym-lib-table
rows = ['(sym_lib_table', '\t(version 7)']
rows.append('\t(lib (name "Singularity_ROBO")(type "KiCad")'
            '(uri "${KIPRJMOD}/Singularity_ROBO.kicad_sym")(options "")'
            '(descr "Project power symbols"))')
for lib, name in USED_LIBSYMS:
    if lib in ('power', 'Device', 'Motor', 'Driver_Motor', 'Driver_LED',
               'Connector', 'Connector_Generic'):
        rows.append(f'\t(lib (name "{lib}")(type "KiCad")'
                    f'(uri "${{KICAD10_SYMBOL_DIR}}/{lib}.kicad_sym")(options "")'
                    f'(descr ""))')
rows.append(')')
with open(os.path.join(ROOT, 'sym-lib-table'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(rows) + '\n')

# --------------------------------------------------------------- project file
pro = json.load(open('/usr/share/kicad/template/kicad.kicad_pro'))
full = json.load(open('/tmp/erctest/RaspberryPi-HAT.kicad_pro'))
pro = {
    'board': full['board'],
    'boards': [],
    'cvpcb': full.get('cvpcb', {'equivalence_files': []}),
    'erc': full['erc'],
    'libraries': {'pinned_footprint_libs': [], 'pinned_symbol_libs': []},
    'meta': {'filename': f'{PROJ}.kicad_pro', 'version': full['meta']['version']},
    'net_settings': full['net_settings'],
    'pcbnew': full['pcbnew'],
    'schematic': full['schematic'],
    'sheets': [[ROOT_UUID, 'Root']],
    'text_variables': {},
}
pro['schematic']['page_layout_descr_file'] = ''
pro['schematic']['plot_directory'] = ''
pro['net_settings']['netclass_assignments'] = {}
pro['net_settings']['netclass_patterns'] = []
with open(os.path.join(ROOT, f'{PROJ}.kicad_pro'), 'w', encoding='utf-8') as f:
    json.dump(pro, f, indent=2)

# --------------------------------------------------------------- expectations
exp = {'named': {k: sorted(list(v)) for k, v in S.expected.items()},
       'unnamed': [sorted(list(g)) for g in S.wire_groups],
       'nc': sorted(list(S.nc_pins)),
       'labels_per_net': {k: sum(1 for l in S.labels if l[0] == k)
                          for k in S.expected}}
with open(os.path.join(ROOT, 'build', 'expected_nets.json'), 'w') as f:
    json.dump(exp, f, indent=1)

# --------------------------------------------------------------- report
npins = sum(len(s['pins']) for s in S.placed.values())
print(f'symbols={len(S.placed)} pins={npins} wires={len(S.wires)} '
      f'labels={len(S.labels)} junctions={len(S.junctions)} '
      f'nc={len(S.ncs)} pwr={S.pwr_n} flags={S.flg_n} texts={len(S.texts)}')
lonely = {k: v for k, v in exp['labels_per_net'].items() if v < 2}
if lonely:
    print('LABELS USED ONLY ONCE (ERC isolated_pin_label):', lonely)
if probs:
    print(f'\n{len(probs)} lint problems:')
    for p in probs:
        print('  -', p)
else:
    print('lint: clean')
