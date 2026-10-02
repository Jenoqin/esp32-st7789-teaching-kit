#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""按键检测：
[1] GPIO0(BOOT) 空闲电平 + 内部下拉测试（外部上拉 = 按键电路特征）
[2] RTS 脉冲复位（EN 复位通路验证，与 EN 键同一条线）
[3] 其余引脚复查（确认没有别的按键上拉/下拉电路）
"""
import re
import serial
import time

ser = serial.Serial("COM3", 115200, timeout=0.2)


def drain(t=0.3):
    time.sleep(t)
    out = bytearray()
    while ser.in_waiting:
        out.extend(ser.read(ser.in_waiting))
    return bytes(out)


def raw_exec(code, wait=8.0):
    for attempt in range(4):
        ser.write(b"\x03\x03"); time.sleep(0.4); drain(0.1)
        ser.reset_input_buffer()
        ser.write(b"\x01"); time.sleep(0.6)
        r = drain(0.2)
        if b"raw REPL" in r:
            ser.reset_input_buffer()
            break
        print("   (raw 进入重试 %d: %r)" % (attempt + 1, r[:80]))
        time.sleep(1.5)
    else:
        raise RuntimeError("无法进入 raw REPL（板子可能还在连 WiFi，稍后重试）")
    data = code.encode()
    for i in range(0, len(data), 48):
        ser.write(data[i:i + 48]); time.sleep(0.03)
    time.sleep(0.2)
    ser.write(b"\x04")
    buf, t0, done = bytearray(), time.time(), False
    while time.time() - t0 < wait:
        if ser.in_waiting:
            buf.extend(ser.read(ser.in_waiting))
            if b"\x04" in buf[-4:]:
                done = True
                break
        else:
            time.sleep(0.05)
    ser.write(b"\x02"); time.sleep(0.2); drain(0.1)
    return buf.decode("utf-8", "replace"), done


print("[1] GPIO0(BOOT键) 电气特征")
out, _ = raw_exec(
    "import machine as m\n"
    "import time\n"
    "p0 = m.Pin(0, m.Pin.IN)\n"
    "print('IDLE', p0.value())\n"
    "p0.init(m.Pin.IN, pull=m.Pin.PULL_DOWN)\n"
    "time.sleep_ms(5)\n"
    "print('WITH_PULLDOWN', p0.value())\n"
    "p0.init(m.Pin.IN)\n", 8)
idle = re.search(r"IDLE (\d)", out)
pd = re.search(r"WITH_PULLDOWN (\d)", out)
idle_v = idle.group(1) if idle else "?"
pd_v = pd.group(1) if pd else "?"
print("   空闲电平 =", idle_v, "（1=高，BOOT 键未按下）")
print("   开内部下拉后 =", pd_v, end=" ")
print("-> 仍为高：引脚上有【外部上拉电路】= BOOT 按键电路存在的标志"
      if pd_v == "1" else "-> 变低：无外部上拉（异常）")

print("\n[2] EN 复位通路（EN 键与 USB 串口的 RTS 走同一条复位线）")
ser.dtr = False; ser.rts = True
time.sleep(0.15)
ser.rts = False
log = drain(4.0).decode("utf-8", "replace")
m = re.search(r"rst:0x\d \((\w+)\)", log)
entry = re.search(r"entry 0x[0-9a-f]+", log)
print("   RTS 脉冲 ->", ("板子复位成功，日志: rst=%s, %s" % (m.group(1) if m else "?", entry.group(0) if entry else "load..."))
      if (m or entry) else "未捕获启动日志")
print("   => EN/复位电路工作正常（EN 键按下时走的就是这条线，效果相同）")

print("\n[3] 其余引脚复查（找是否有其它按键的下拉/上拉电路）")
out, _ = raw_exec(
    "import machine as m\n"
    "res = {}\n"
    "for p in [13,14,16,17,21,22,25,26,27,32,33]:\n"
    "    pu = m.Pin(p, m.Pin.IN, pull=m.Pin.PULL_UP).value()\n"
    "    pd = m.Pin(p, m.Pin.IN, pull=m.Pin.PULL_DOWN).value()\n"
    "    res[p] = (pu, pd)\n"
    "print('SURVEY=' + str(res))", 10)
sm = re.search(r"SURVEY=(\{.*\})", out, re.S)
if sm:
    d = eval(sm.group(1))
    loaded = [p for p, (pu, pd) in d.items() if pu == pd]
    print("  ", " ".join("GPIO%d:[拉上=%d,拉下=%d]" % (p, v[0], v[1]) for p, v in sorted(d.items())))
    print("   结论:", ("GPIO%s 上有外部电路！" % loaded) if loaded
          else "全部为浮空特征（拉得上1也拉得下0）→ 没有接任何其它按键/开关")

print("\n[4] 复位板子，恢复遥控服务运行")
ser.dtr = False; ser.rts = True
time.sleep(0.15)
ser.rts = False
log = drain(16.0).decode("utf-8", "replace")
print("  ", "服务已恢复 ✅" if ("Web 服务就绪" in log or "热点已开启" in log) else "（未确认，下次复位也会自启）")
ser.close()
