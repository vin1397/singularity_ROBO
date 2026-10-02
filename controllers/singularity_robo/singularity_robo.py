from controller import Robot, Keyboard
robot=Robot(); timestep=int(robot.getBasicTimeStep())
left=robot.getDevice("left_motor"); right=robot.getDevice("right_motor")
la=robot.getDevice("left_arm"); ra=robot.getDevice("right_arm"); head=robot.getDevice("head_yaw")
sensor=robot.getDevice("person_sensor"); camera=robot.getDevice("camera")
left.setPosition(float("inf")); right.setPosition(float("inf"))
left.setVelocity(0); right.setVelocity(0)
for m in (la,ra,head): m.setPosition(0)
sensor.enable(timestep); camera.enable(timestep)
kb=Keyboard(); kb.enable(timestep)
MAX=5.0; namaste=False; start=0.0; last_person=False

def namaste_start():
    global namaste,start
    namaste=True; start=robot.getTime()

while robot.step(timestep)!=-1:
    forward=turn=0; key=kb.getKey()
    while key!=-1:
        if key in (Keyboard.UP,ord('W'),ord('w')): forward=1
        elif key in (Keyboard.DOWN,ord('S'),ord('s')): forward=-1
        elif key in (Keyboard.LEFT,ord('A'),ord('a')): turn=1
        elif key in (Keyboard.RIGHT,ord('D'),ord('d')): turn=-1
        elif key in (ord('N'),ord('n')): namaste_start()
        key=kb.getKey()
    if namaste: forward=turn=0
    left.setVelocity(max(-MAX,min(MAX,(forward+turn)*MAX)))
    right.setVelocity(max(-MAX,min(MAX,(forward-turn)*MAX)))
    d=sensor.getValue()
    person=(d>0 and d<1.2)
    if person and not last_person and not namaste: namaste_start()
    last_person=person
    if namaste:
        t=robot.getTime()-start
        if t<0.7:
            p=t/0.7; la.setPosition(-0.9*p); ra.setPosition(0.9*p)
        elif t<1.8:
            la.setPosition(-0.9); ra.setPosition(0.9)
        elif t<2.5:
            p=(t-1.8)/0.7; la.setPosition(-0.9*(1-p)); ra.setPosition(0.9*(1-p))
        else:
            la.setPosition(0); ra.setPosition(0); namaste=False
