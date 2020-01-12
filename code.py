import board
import pulseio
import busio
import time
import supervisor
import neopixel

pixel = neopixel.NeoPixel(board.NEOPIXEL, 1)
pixel[0] = 0

tv = busio.UART(board.D12, board.D5)
receiver = busio.UART(board.TX, board.RX)

p = pulseio.PulseIn(board.A0, maxlen=256, idle_state=True)

class UnknownProtocol:
    def __init__(self, pulse_source):
        self._pulse_source = pulse_source
        self._skip = 0

    def __iter__(self):
        return self

    def __next__(self):
        last_command = None
        while True:
            if len(self._pulse_source) >= 23:
                if self._skip == 0:
                    self._skip = 1
                else:
                    for i in range(self._skip):
                        while len(self._pulse_source) == 0:
                            pass
                    #     print("discard", i, self._pulse_source.popleft())
                    # print("done discarding")
                    if self._skip > 1:
                        self._skip = 1
                        continue
                value = 0
                for i in range(11):
                    e = self._pulse_source.popleft()
                    if e > 2000:
                        # print("skip", e)
                        if 9000 < e < 9400:
                            self._skip = 65
                        else:
                            self._skip = 0
                        break
                    o = self._pulse_source.popleft()
                    if o > 2000:
                        # print("skip", o)
                        if 9000 < o < 9400:
                            self._skip = 65
                        else:
                            self._skip = 0
                        break
                    value <<= 2
                    if e > 1000:
                        value |= 2
                    if o > 1000:
                        value |= 1
                    #print(i, e, o)
                if self._skip == 1:
                    # print(self._pulse_source.popleft())
                    return value
                # print()

decoder = UnknownProtocol(p)

current_power = False
last_power = 0
last_mute = 0
last_button = 0
receiver.write(b"\r")
receiver.write(b"MV?\r")
response = receiver.read(14)
print(response)
if not response:
    print("reloading in 30s")
    pixel[0] = 0x220000
    time.sleep(30)
    supervisor.reload()

pixel[0] = 0x002200

if response[-1] != '\r':
    receiver.read(1)
v, max_v = response.split(b'\r')[:2]
volume = int(v[2:4])


receiver.write(b"MU?\r")
response = receiver.read(5)
print(response, response[-2], ord('N'))
mute = response[-2] == ord('N')
print(mute)
if mute:
    receiver.read(1)

for command in decoder:
    button = command & 0xff
    command = command & 0xe00ff
    if button != last_button:
        last_button = button
        continue

    now = time.monotonic()
    if button == 18: # Power
        if now - last_power > 4:
            print("toggle power", current_power)
            if current_power:
                tv.write(b"ka 01 00\r")
                receiver.write(b"PWSTANDBY\r")
            else:
                tv.write(b"ka 01 01\r")
                receiver.write(b"PWON\r")
            time.sleep(0.2)
            print(tv.read())
            print(receiver.read())
            current_power = not current_power
        last_power = time.monotonic()
    elif button == 97:
        volume -= 1
        print("volume down", volume)
        receiver.write("MV{}0\r".format(volume).encode("utf-8"))
        count = 0
        while count < 2:
            if receiver.read(1) == b'\r':
                count += 1
    elif button == 96:
        volume += 1
        print("volume up", volume)
        receiver.write(b"MV{}0\r".format(volume).encode("utf-8"))
        count = 0
        while count < 2:
            if receiver.read(1) == b'\r':
                count += 1
    elif button == 19:
        if now - last_mute > 0.5:
            print("toggle mute", mute)
            if mute:
                receiver.write(b"MUOFF\r")
            else:
                receiver.write(b"MUON\r")

            count = 0
            while count < 1:
                b = receiver.read(1)
                if b == b'\r':
                    count += 1
            mute = not mute
        last_mute = now
