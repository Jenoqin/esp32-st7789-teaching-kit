#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""读回板子上的 web_screen_remote.py，与 PC 版本对比，确认改动不会丢失"""
import difflib
import serial
import time

ser = serial.Serial("COM3", 115200, timeout=0.2)
time.sleep(0.5)
ser.reset_input_buffer()

# Ctrl+A 进 raw REPL
ser.write(b"\x03\x03"); time.sleep(0.3)
ser.read(ser.in_waiting)
ser.write(b"\x01"); time.sleep(0.5)
r = ser.read(ser.in_waiting)
assert b"raw REPL" in r, r
ser.reset_input_buffer()

code = b"import sys\nf=open('web_screen_remote.py').read()\nfor i in range(0, len(f), 400):\n    print(f[i:i+400])\n"
for i in range(0, len(code), 48):
    ser.write(code[i:i+48]); time.sleep(0.03)
time.sleep(0.3)
ser.write(b"\x04")
buf, t0 = bytearray(), time.time()
while time.time() - t0 < 25:
    if ser.in_waiting:
        buf.extend(ser.read(ser.in_waiting))
        if b"\x04" in buf[-4:]:
            break
    else:
        time.sleep(0.05)
ser.write(b"\x02"); time.sleep(0.2)

text = buf.decode("utf-8", "replace")
# 去掉回显的命令行和首尾控制符，取第一个 'import sys' 之后的正文
start = text.find("# -*- coding")
end = text.rfind("\x04")
body = text[start:end if end > 0 else len(text)]
body = body.replace("\r\n", "\n")

pc = open("web_screen_remote.py", encoding="utf-8").read().replace("\r\n", "\n")
# 板子是按 400 字符/块 print 的（块尾带 \n），PC 侧按同样方式分块后对比
pc_stream = "\n".join(pc[i:i + 400] for i in range(0, len(pc), 400))
open("logs/board_copy_current.py", "w", encoding="utf-8").write(body)
print("板子 %d 字符 / PC(分块后) %d 字符" % (len(body), len(pc_stream)))

if body == pc_stream:
    print("内容一致（PC 版为最新，板上无额外改动）")
else:
    import difflib
    diff = list(difflib.unified_diff(pc_stream.splitlines(), body.splitlines(),
                                     "pc", "board", lineterm="", n=1))
    print("真实差异 %d 行：" % len(diff))
    print("\n".join(diff[:60]))
