#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BOOT 键切换画面·端到端验证（无需人手按键）

原理：板的自动下载电路里 CP210x 的 DTR 经三极管接 IO0（=GPIO0）。
设 DTR=1 且 RTS=0 时 IO0 被拉低、EN 保持高（不复位）——
等效于"按住 BOOT 键"，运行中的程序就会检测到按下沿。
"""
import re
import serial
import time

ser = serial.Serial("COM3", 115200, timeout=0.2)
ser.dtr = False
ser.rts = False


def drain(t=0.3):
    time.sleep(t)
    out = bytearray()
    while ser.in_waiting:
        out.extend(ser.read(ser.in_waiting))
    return bytes(out)


def press_boot(seconds=0.35):
    """电控模拟按一下 BOOT 键"""
    ser.dtr = True
    ser.rts = False          # DTR=1, RTS=0 -> IO0 低, EN 高（不复位）
    time.sleep(seconds)
    ser.dtr = False          # 松开
    time.sleep(0.05)


print("[1] 复位，等服务起来（自动运行 web_screen_remote）")
ser.dtr = False; ser.rts = True
time.sleep(0.15)
ser.rts = False
log = drain(18.0).decode("utf-8", "replace")
ready = ("Web 服务就绪" in log) or ("热点已开启" in log)
start = re.findall(r"MODE -> (\w+)", log)
print("   服务就绪:", ready, "| 启动画面:", start)
if not ready:
    print(log[-600:])
    raise SystemExit(1)

print("\n[2] 连续电按 BOOT 键，验证画面循环 HELLO→CLOCK→ROBOT→WEATHER→OFF→HELLO")
expect = ["CLOCK", "ROBOT", "WEATHER", "OFF", "HELLO"]
all_ok = True
for want in expect:
    press_boot()
    wait = 10 if want == "WEATHER" else 4     # 天气画面会先抓 API
    chunk = drain(wait).decode("utf-8", "replace")
    got = re.findall(r"MODE -> (\w+)", chunk)
    wx = re.findall(r"WX: .+", chunk)
    ok = want in got
    all_ok &= ok
    extra = (" | " + wx[0].strip()) if wx else ""
    print("   按下 -> 期望 %-7s 实际 %-7s %s%s"
          % (want, got[0] if got else "(无)", "✅" if ok else "❌", extra))
    if not ok:
        print("   串口尾部:", chunk[-300:])

print("\n[3] 复查：没有发生误复位（全程应无 boot 日志插入）")
press_boot()
chunk = drain(4).decode("utf-8", "replace")
no_reset = "POWERON_RESET" not in chunk and "entry 0x" not in chunk
print("   按键期间无复位日志:", no_reset, "| 本次切换:",
      re.findall(r"\[BOOT键\] 切换 -> (\w+)", chunk))

print("\n结果:", "✅ BOOT 键切屏功能全链路通过" if all_ok and no_reset else "❌ 有失败项，见上")
ser.close()
