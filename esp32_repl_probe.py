#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
通过 MicroPython REPL 查询 ESP32 与 OLED 状态（只读探测）
- 打开串口后等待启动完成，避免命令被复位吞掉
- 扫描常见引脚组合，定位 OLED 的 I2C 地址
"""
import sys
import time
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200

# 已知：本机屏幕是 SPI TFT，不要用 I2C 扫描探测（会抢占引脚）
# 这里保留一份 I2C OLED 的常见接法，仅供「换用 I2C 屏」时参考，脚本不会去扫。
I2C_OLED_REFERENCE = [
    (22, 21),   # SSD1306 最常见接法 (SCL, SDA)
    (18, 19),
]


def open_and_settle(port, baud=BAUD, settle=3.0):
    """打开串口并等待模组启动完成，返回 (ser, boot_log)"""
    ser = serial.Serial(port, baud, timeout=0.2)
    ser.reset_input_buffer()
    boot = bytearray()
    t0 = time.time()
    while time.time() - t0 < settle:
        n = ser.in_waiting
        if n:
            boot.extend(ser.read(n))
        else:
            time.sleep(0.05)
    ser.reset_input_buffer()
    return ser, bytes(boot)


def repl(ser, cmd, wait=3.0):
    """发送一条命令，返回 REPL 回显"""
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
    """剥掉 REPL 对命令本身的回显"""
    out = []
    started = False
    for line in text.splitlines():
        if not started and cmd.strip()[:20] in line:
            started = True
            continue
        out.append(line)
    return "\n".join(out).strip()


def main():
    print("=" * 64)
    print(f"  ESP32 MicroPython REPL 探测  @ {PORT}")
    print("=" * 64)

    ser, boot = open_and_settle(PORT)
    print("\n[启动日志]")
    print(boot.decode("utf-8", errors="replace").strip() or "  (空)")

    print("\n" + "-" * 64)
    print("[1] 系统与固件信息")
    print("-" * 64)
    cmds = [
        "import os, esp, gc, machine, sys",
        "print(os.uname())",
        "print('FLASH_MB =', esp.flash_size()//1048576)",
        "print('CPU_MHz  =', machine.freq()//1000000)",
        "print('RAM_FREE =', gc.mem_free(), ' RAM_USED =', gc.mem_alloc())",
        "print('FREQ_RAW =', machine.freq())",
    ]
    for c in cmds:
        r = strip_echo(repl(ser, c), c)
        print(f"  > {c}\n    {r if r else '(无输出)'}")

    print("\n" + "-" * 64)
    print("[2] 文件系统（看有没有 main.py / boot.py / oled 驱动）")
    print("-" * 64)
    for c in ["import os; print(os.listdir('/'))",
              "print([f for f in os.listdir('/') if f.endswith('.py')])"]:
        r = strip_echo(repl(ser, c), c)
        print(f"  > {c}\n    {r if r else '(无输出)'}")

    print("\n" + "-" * 64)
    print("[3] 显示屏接口：直接读代码里的引脚定义（不重新配置引脚）")
    print("-" * 64)
    print("  注意：本机屏幕是 SPI 接口，不要用 I2C.scan() 盲扫！")
    print("  盲扫会把 SCK / BL(背光) / CS / RST 等引脚强行改成 I2C 功能，")
    print("  导致屏幕熄灭或花屏。下面只做只读解析。\n")
    src = repl(ser, "print(open('main.py').read())", wait=4.0)
    import re as _re
    # 支持两种写法：
    #   SCK, MOSI, CS, DC, RST, BL = 18, 23, 5, 2, 4, 19   (连续赋值)
    #   SCK = 18 ; MOSI = 23                                (逐个赋值)
    pins = {}
    mv = _re.search(
        r"\b([A-Z][A-Za-z_]*(?:\s*,\s*[A-Z][A-Za-z_]*)+)\s*=\s*(\d+(?:\s*,\s*\d+)+)",
        src)
    if mv:
        names = [x.strip() for x in mv.group(1).split(",")]
        vals = [x.strip() for x in mv.group(2).split(",")]
        if len(names) == len(vals):
            pins = dict(zip(names, vals))
    # 逐个赋值只做补充，绝不覆盖连续赋值的结果
    # （否则 "..., BL = 18, ..., 19" 会被误读成 BL=18）
    for k, v in dict(_re.findall(r"\b(SCK|MOSI|MISO|CS|DC|RST|BL)\s*=\s*(\d+)", src)).items():
        pins.setdefault(k, v)
    res = _re.search(r"WIDTH,\s*HEIGHT\s*=\s*(\d+),\s*(\d+)", src)
    text = _re.search(r"TEXT\s*=\s*['\"]([^'\"]+)['\"]", src)
    spi = _re.search(r"SPI\((\d+)", src)
    print("  解析到的接线：")
    if pins:
        for k in ["SCK", "MOSI", "CS", "DC", "RST", "BL"]:
            if k in pins:
                print(f"    {k:<5} = GPIO{pins[k]}")
    if res:
        print(f"    分辨率 = {res.group(1)} x {res.group(2)}")
    if spi:
        print(f"    SPI 总线 = SPI({spi.group(1)})")
    if text:
        print(f"    显示文本 = {text.group(1)!r}")
    if not pins:
        print("    (未能从 main.py 解析到引脚，请手动查看源码)")

    print("\n" + "=" * 64)
    ser.close()


if __name__ == "__main__":
    main()
