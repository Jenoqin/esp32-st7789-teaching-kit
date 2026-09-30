#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ESP32 深度信息探测（只读）
- 芯片 / Flash / MAC / 传感器
- 直接读显示驱动 IC 的 ID 与状态寄存器，确认屏幕型号
"""
import sys
import time
import re
import serial

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM3"
BAUD = 115200

# JEDEC Flash 制造商
FLASH_VENDORS = {
    0xEF: "Winbond", 0xC8: "GigaDevice(兆易创新)", 0x20: "ST/Numonyx",
    0x1C: "Eon(宜扬)", 0x5E: "Zbit/Zetta", 0x0B: "XMC(武汉新芯)",
    0x9D: "ISSI", 0xC2: "Macronix(旺宏)", 0xBF: "Microchip/SST",
    0xAD: "Hyundai", 0x01: "AMD/Spansion", 0x1F: "Atmel",
    0x68: "Boya(博雅)", 0x85: "Puya(普冉)", 0xA1: "Fudan Micro(复旦微)",
}
# 常见显示驱动 IC 的 RDDID 特征 (id1,id2,id3) -> 型号
LCD_IDS = {
    (0x00, 0x93, 0x41): "ILI9341",
    (0x00, 0x93, 0x40): "ILI9340 / ILI9341 兼容",
    (0x00, 0x85, 0x85): "ST7789 / ST7789V",
    (0x00, 0x85, 0x52): "ST7789 变体",
    (0x00, 0x77, 0x89): "ST7735",
    (0x00, 0x7C, 0x89): "ST7735S",
    (0x00, 0x54, 0x85): "ILI9488 / 兼容",
    (0x00, 0x94, 0x88): "ILI9488",
    (0x00, 0x93, 0x61): "ILI9342C",
    (0x00, 0x15, 0x15): "ILI9163",
}


def open_and_settle(port, baud=BAUD, settle=3.5):
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


def out(ser, cmd, wait=3.0):
    """发送命令并打印去掉回显后的结果"""
    r = repl(ser, cmd, wait)
    lines = r.splitlines()
    body = []
    started = False
    for ln in lines:
        if not started and cmd.strip()[:24] in ln:
            started = True
            continue
        body.append(ln)
    txt = "\n".join(body).strip()
    # 去掉尾部提示符
    txt = re.sub(r"\n?>>>\s*$", "", txt).strip()
    print(f"  > {cmd}")
    print(f"    {txt if txt else '(无输出)'}")
    return txt


def main():
    ser, boot = open_and_settle(PORT)

    print("=" * 66)
    print(f"  ESP32 深度硬件探测  @ {PORT}")
    print("=" * 66)

    print("\n" + "-" * 66)
    print("[A] 芯片与固件")
    print("-" * 66)
    out(ser, "import os, esp, esp32, machine, gc, network", wait=2.0)
    out(ser, "print(os.uname())")
    out(ser, "print('ROM_DATE:', open('/').__class__ and 'n/a')", wait=1.5)
    uname = out(ser, "print(os.uname().machine)")

    print("\n" + "-" * 66)
    print("[B] Flash 芯片（含厂商 JEDEC ID）")
    print("-" * 66)
    # 注意：部分 MicroPython 构建裁掉了 esp.flash_id()，用 getattr 兜底
    # 拿不到时用 esptool 的 `flash-id` 命令，信息更权威
    fid = out(ser, "print('FLASH_ID =', hex(getattr(esp, 'flash_id', lambda: 0)()))")
    out(ser, "print('SIZE_MB =', esp.flash_size()//1048576, ' BYTES =', esp.flash_size())")
    m = re.search(r"0x([0-9a-fA-F]{6})", fid)
    if m:
        raw = int(m.group(1), 16)
        mid = (raw >> 16) & 0xFF
        mtype = (raw >> 8) & 0xFF
        cap = raw & 0xFF
        vendor = FLASH_VENDORS.get(mid, "未知厂商")
        mb = (1 << cap) / 1048576 if cap >= 0x13 else None
        print(f"    -> 厂商 = {vendor} (0x{mid:02X})")
        print(f"    -> 类型 = 0x{mtype:02X}")
        print(f"    -> 容量码 = 0x{cap:02X}" + (f"  约 {mb:.0f} MB" if mb else ""))
    out(ser, "print('PSRAM =', getattr(esp, 'psram_size', lambda: 0)())")

    print("\n" + "-" * 66)
    print("[C] 无线与身份标识")
    print("-" * 66)
    out(ser, "print('STA_MAC  =', ':'.join('%02X'%b for b in network.WLAN(network.STA_IF).config('mac')))")
    out(ser, "print('AP_MAC   =', ':'.join('%02X'%b for b in network.WLAN(network.AP_IF).config('mac')))")

    print("\n" + "-" * 66)
    print("[D] ESP32 特征外设（区分 ESP32 / S2 / S3 / C3）")
    print("-" * 66)
    # 这版构建未编译 hall_sensor / mcu_temperature，用 getattr 兜底避免中断
    out(ser, "print('HALL_SENSOR =', getattr(esp32, 'hall_sensor', lambda: 'N/A')())")
    out(ser, "print('MCU_TEMP_C  =', getattr(esp32, 'mcu_temperature', lambda: 'N/A')())")
    out(ser, "import _thread; print('THREADS =', 'yes')")
    out(ser, "print('TOUCH_PAD_EXISTS =', hasattr(esp32, 'TouchPad'))")

    print("\n" + "-" * 66)
    print("[E] 存储与内存")
    print("-" * 66)
    out(ser, "import os; st=os.statvfs('/'); print('FS_TOTAL_KB =', st[0]*st[2]//1024, ' FS_FREE_KB =', st[0]*st[3]//1024)")
    out(ser, "print('RAM_FREE =', gc.mem_free(), ' RAM_USED =', gc.mem_alloc())")

    print("\n" + "-" * 66)
    print("[F] 显示屏：读驱动 IC 的 ID 与状态寄存器")
    print("-" * 66)
    print("  说明：复用 main.py 中的 SPI 引脚(18/23/5/2/19)，不改动接线。")
    print("  重要：WLK1501SPI-8P 是 8 针版本，未引出 SDO/MISO，屏幕只写不读。")
    print("        所以下面读 0x04(RDDID) 必然返回全 0，属预期结果，不是故障。")
    # 建立与 main.py 完全相同的 SPI 配置
    out(ser, "from machine import Pin, SPI", wait=2.0)
    out(ser, "spi = SPI(1, baudrate=20000000, polarity=0, phase=0, sck=Pin(18), mosi=Pin(23), miso=Pin(34))", wait=2.0)
    out(ser, "cs = Pin(5, Pin.OUT, value=1); dc = Pin(2, Pin.OUT, value=1)", wait=2.0)

    def rd(cmd_byte, n, label):
        c = (f"dc.value(0); cs.value(0); spi.write(bytes([{cmd_byte}])); "
             f"dc.value(1); d=spi.read({n}); cs.value(1); "
             f"print('{label}', d.hex(' '))")
        return out(ser, c, wait=3.0)

    haddr = rd(0x04, 4, "RDDID  0x04:")
    rddid = re.search(r"RDDID\s+0x04:\s*([0-9a-f ]+)", haddr)
    if rddid:
        bs = [int(x, 16) for x in rddid.group(1).split()]
        # 取最后 3 字节作为 ID（第一字节常为 dummy）
        for trio in [bs[-3:], bs[:3]]:
            if len(trio) == 3:
                key = tuple(trio)
                if key in LCD_IDS:
                    print(f"    >>> 驱动 IC 判定：{LCD_IDS[key]}")
                    break
        else:
            print(f"    >>> 未匹配已知型号，原始 ID = {bs}")

    rd(0x09, 5, "STATUS 0x09:")   # read display status
    rd(0x0A, 2, "POWER  0x0A:")   # read display power mode
    rd(0x0B, 2, "MADCTL 0x0B:")   # read display MADCTL
    rd(0x0C, 2, "PIXFMT 0x0C:")   # read display pixel format
    rd(0x0D, 2, "IMGFMT 0x0D:")   # read display image format

    print("\n" + "-" * 66)
    print("[G] boot.py（看是否有额外初始化）")
    print("-" * 66)
    out(ser, "print(open('boot.py').read())", wait=4.0)

    print("\n" + "=" * 66)
    ser.close()


if __name__ == "__main__":
    main()
