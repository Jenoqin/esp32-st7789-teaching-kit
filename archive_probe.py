#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
归档探测（2026-09-30）：一次性采集
  1. 完整启动日志（含 main.py 执行完的 HELLO SHOWN）
  2. 固件 / RAM / 文件系统 / MAC
  3. main.py 引脚定义（连线的事实来源）
  4. 空闲 GPIO 电气状态调查（区分 浮空 / 被外部拉高 / 被外部拉低）
     —— 只碰安全引脚：跳过屏幕引脚(2,4,5,18,19,23)、strapping(12,15 只读不改)、
        UART0(1,3)、BOOT 键(0 只读)。绝不做 I2C 盲扫。
"""
import sys
import time
import re
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200


def reset_and_capture(ser, seconds=10.0):
    """拉 RTS 复位板子并抓完整启动日志"""
    ser.dtr = False
    ser.rts = True
    time.sleep(0.15)
    ser.rts = False
    ser.dtr = False
    buf = bytearray()
    t0 = time.time()
    while time.time() - t0 < seconds:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        else:
            time.sleep(0.05)
    return bytes(buf)


def repl(ser, cmd, wait=2.5):
    ser.reset_input_buffer()
    ser.write(cmd.encode() + b"\r\n")
    buf = bytearray()
    t0 = time.time()
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        else:
            time.sleep(0.04)
    return buf.decode("utf-8", errors="replace")


def strip_echo(text, cmd):
    out, started = [], False
    key = cmd.strip()[:20]
    for line in text.splitlines():
        if not started and key in line:
            started = True
            continue
        out.append(line)
    txt = "\n".join(out).strip()
    return re.sub(r"\n?>>>\s*$", "", txt).strip()


def q(ser, cmd, wait=2.5, label=None):
    r = strip_echo(repl(ser, cmd, wait), cmd)
    print(f"  > {label or cmd}")
    for ln in r.splitlines():
        print(f"    {ln}")
    if not r:
        print("    (无输出)")
    return r


def raw_paste(ser, code, wait=8.0):
    """raw REPL（Ctrl+E）执行整段代码：无回显/自动缩进/续行问题。
    分块发送避免 UART RX FIFO（128B）溢出。"""
    ser.write(b"\x03\x03")
    time.sleep(0.2)
    ser.reset_input_buffer()
    ser.write(b"\x05")  # Ctrl+E 进入 raw REPL
    time.sleep(0.4)
    ser.reset_input_buffer()
    data = code.encode()
    for i in range(0, len(data), 48):
        ser.write(data[i:i + 48])
        time.sleep(0.03)
    time.sleep(0.2)
    ser.write(b"\x04")  # Ctrl+D 执行
    buf, t0 = bytearray(), time.time()
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        else:
            time.sleep(0.03)
    out = buf.decode("utf-8", errors="replace")
    ser.write(b"\x02")  # Ctrl+B 回到普通 REPL
    time.sleep(0.2)
    ser.reset_input_buffer()
    return out


def main():
    ser = serial.Serial(PORT, BAUD, timeout=0.2)
    time.sleep(0.3)
    ser.reset_input_buffer()

    print("=" * 66)
    print(f"  归档探测 @ {PORT}  {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 66)

    print("\n[A] 完整启动日志（复位后监听 10 秒）")
    print("-" * 66)
    boot = reset_and_capture(ser, 10.0)
    txt = boot.decode("utf-8", errors="replace")
    for ln in txt.splitlines():
        if ln.strip():
            print(f"  | {ln}")
    print(f"\n  >>> {'HELLO SHOWN 出现，屏幕主程序执行正常' if 'HELLO SHOWN' in txt else '!! 未捕获 HELLO SHOWN（main.py 可能未跑完或已改动）'}")

    print("\n[B] 固件 / 频率 / RAM / 存储")
    print("-" * 66)
    q(ser, "import os, esp, machine, gc, network", wait=2.0)
    q(ser, "print(os.uname())")
    q(ser, "print('CPU_MHz =', machine.freq() // 1000000)")
    q(ser, "print('FLASH_BYTES =', esp.flash_size())")
    q(ser, "print('PSRAM_BYTES =', getattr(esp, 'psram_size', lambda: 0)())")
    q(ser, "st = os.statvfs('/'); print('FS_TOTAL_KB =', st[0]*st[2]//1024, ' FS_FREE_KB =', st[0]*st[3]//1024)")
    q(ser, "print('RAM_FREE =', gc.mem_free(), ' RAM_USED =', gc.mem_alloc())")

    print("\n[C] MAC 地址")
    print("-" * 66)
    q(ser, "print('STA_MAC =', ':'.join('%02X'%b for b in network.WLAN(network.STA_IF).config('mac')))")
    q(ser, "print('AP_MAC  =', ':'.join('%02X'%b for b in network.WLAN(network.AP_IF).config('mac')))")

    print("\n[D] 板载文件清单")
    print("-" * 66)
    q(ser, "print([(f, os.stat(f)[6]) for f in sorted(os.listdir('/'))])")

    print("\n[E] main.py 全文（连线的事实来源）")
    print("-" * 66)
    main_src = repl(ser, "print(open('main.py').read())", wait=4.0)
    for ln in main_src.splitlines():
        if ln.strip() and "print(open" not in ln:
            print(f"  | {ln}")

    print("\n[F] 空闲 GPIO 电气状态调查（区分 浮空/外部拉高/外部拉低）")
    print("-" * 66)
    survey_code = (
        "import machine as m\n"
        "res={}\n"
        "for p in [0,12,15]: res[p]=[m.Pin(p,m.Pin.IN).value()]\n"
        "for p in [13,14,16,17,21,22,25,26,27,32,33]: res[p]=[m.Pin(p,m.Pin.IN).value()]\n"
        "for p in [13,14,16,17,21,22,25,26,27,32,33]: res[p].append(m.Pin(p,m.Pin.IN,pull=m.Pin.PULL_UP).value())\n"
        "for p in [13,14,16,17,21,22,25,26,27,32,33]: res[p].append(m.Pin(p,m.Pin.IN,pull=m.Pin.PULL_DOWN).value())\n"
        "for p in [34,35,36,39]: res[p]=[m.Pin(p,m.Pin.IN).value()]\n"
        "print('SURVEY='+str(res))\n"
    )
    r = raw_paste(ser, survey_code, wait=8.0)
    m = re.search(r"SURVEY=(\{.*\})", r, re.S)
    d = {}
    if m:
        try:
            d = eval(m.group(1))  # 受控来源：本脚本生成的 MicroPython 代码输出
        except Exception as e:
            print(f"  (eval 失败: {e})")
    if d:
        print("  GPIO: [无上拉读值, 上拉读值, 下拉读值] / 只读脚: [读值]")
        print("  判读: 浮空=[x,1,0] | 外部拉低/重负载=[x,0,0] | 外部拉高=[x,1,1]")
        for p in sorted(d):
            print(f"    GPIO{p:<3} = {d[p]}")
    else:
        print(f"  (未取到调查数据，原始回显尾部)")
        for ln in r.splitlines()[-25:]:
            if ln.strip():
                print(f"  | {ln}")

    print("\n" + "=" * 66)
    ser.close()
    print("完成。")


if __name__ == "__main__":
    main()
