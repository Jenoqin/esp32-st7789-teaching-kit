#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ESP32-WROOM 模组 + OLED 状态检测脚本
功能:
  1. 枚举本机所有串口，识别 ESP32 常见 USB 桥接芯片 (CP210x / CH34x / FTDI)
  2. 对候选端口做「非侵入式」探测: DTR/RTS 拉高 -> 读取串口自发日志
  3. 输出波特率、日志内容、是否为 ESP32 boot log / MicroPython REPL 等判断
用法:
  python esp32_check.py             # 全量检测
  python esp32_check.py COM3        # 只检测指定端口
"""

import sys
import time
import threading

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("[错误] 缺少 pyserial，请先执行: pip install pyserial")
    sys.exit(1)

# ESP32 上电启动日志的特征串
ESP32_BOOT_MARKERS = [
    "rst:0x", "boot:", "ets Jun", "ESP-IDF", "esp-idf",
    "SPIWP", "mode:DIO", "load:0x", "entry 0x",
    "chip revision", "Brownout detector",
]
MICROPYTHON_MARKERS = ["MicroPython", ">>>", "MPY:", "Type \"help()\""]
ARDUINO_MARKERS = ["Arduino", "setup()", "loop()"]

COMMON_BAUDS = [115200, 921600, 460800, 230400, 57600, 9600]


def list_ports():
    """枚举串口，返回 (port_info, is_esp32_candidate)"""
    ports = list(serial.tools.list_ports.comports())
    results = []
    for p in ports:
        hwid = (p.hwid or "").upper()
        desc = (p.description or "").upper()
        vid = p.vid
        pid = p.pid
        # ESP32 开发板常见 USB-UART 桥接
        cand = False
        chip = "未知"
        if vid == 0x10C4 or "CP210" in hwid or "CP210" in desc:
            cand, chip = True, "Silicon Labs CP210x"
        elif vid == 0x1A86 or "CH34" in hwid or "CH34" in desc or "CH340" in desc:
            cand, chip = True, "WCH CH34x"
        elif vid == 0x0403 or "FTDI" in hwid or "FT232" in desc:
            cand, chip = True, "FTDI FT232"
        elif vid == 0x303A or "ESP32" in desc or "USB JTAG" in desc:
            cand, chip = True, "Espressif 原生 USB"
        results.append((p, cand, chip))
    return results


def probe_port(port_name, baudrate=115200, listen_seconds=4.0):
    """打开串口监听自发日志。不发送任何数据，只读。"""
    log = bytearray()
    err = None
    try:
        ser = serial.Serial(
            port=port_name,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=0.2,
            # 关键: 先不拉 DTR/RTS，避免误复位; 仅在需要复位时才操作
        )
        try:
            # 尝试复位一次以抓取 boot log (多数 ESP32 板 DTR->GPIO0, RTS->EN)
            try:
                ser.dtr = False
                ser.rts = True
                time.sleep(0.15)
                ser.rts = False
                ser.dtr = False
            except Exception:
                pass

            deadline = time.time() + listen_seconds
            while time.time() < deadline:
                n = ser.in_waiting
                if n:
                    log.extend(ser.read(n))
                else:
                    time.sleep(0.05)
        finally:
            ser.close()
    except Exception as e:
        err = str(e)
    return bytes(log), err


def analyze(data: bytes):
    """分析抓到的日志，判断运行状态"""
    if not data:
        return "无数据（端口空闲，程序可能未打印日志，或波特率不匹配）", []
    try:
        text = data.decode("utf-8", errors="replace")
    except Exception:
        text = repr(data)
    hits = []
    for m in ESP32_BOOT_MARKERS:
        if m in text:
            hits.append(("ESP32 启动日志", m))
    for m in MICROPYTHON_MARKERS:
        if m in text:
            hits.append(("MicroPython", m))
    for m in ARDUINO_MARKERS:
        if m in text:
            hits.append(("Arduino", m))
    if hits:
        kinds = sorted(set(k[0] for k in hits))
        return " / ".join(kinds), hits
    return "收到未知格式数据（可能是自定义固件输出）", []


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    print("=" * 62)
    print("  ESP32-WROOM + OLED  设备状态检测")
    print("=" * 62)

    ports = list_ports()
    print(f"\n[1] 本机串口扫描完成，共发现 {len(ports)} 个串行端口：\n")
    if not ports:
        print("    未发现任何串口设备！请检查：")
        print("    - USB 线是否为『数据线』（部分充电线只有电源线）")
        print("    - 驱动是否安装（CP210x / CH340 需单独装驱动）")
        print("    - 设备管理器中是否有黄色感叹号")
        return

    candidates = []
    for p, cand, chip in ports:
        vidpid = ""
        if p.vid and p.pid:
            vidpid = f" [VID:PID={p.vid:04X}:{p.pid:04X}]"
        flag = "  <== ESP32 候选" if cand else ""
        print(f"    {p.device:<8} {p.description}{vidpid}{flag}")
        if cand:
            print(f"             桥接芯片: {chip}")
        if cand:
            candidates.append(p.device)

    if target:
        candidates = [target]

    if not candidates:
        print("\n[!] 未识别出典型 ESP32 桥接芯片，将逐个探测所有端口。")
        candidates = [p.device for p, _, _ in ports]

    print("\n[2] 串口日志监听（各端口约 6 秒）...\n")
    for dev in candidates:
        print("-" * 62)
        print(f"  端口 {dev}:")
        got_any = False
        for baud in COMMON_BAUDS:
            data, err = probe_port(dev, baud, listen_seconds=2.0)
            if err:
                print(f"    打开失败({baud}): {err}")
                break
            if data:
                got_any = True
                kind, hits = analyze(data)
                print(f"    波特率 {baud} -> 收到 {len(data)} 字节，判定: {kind}")
                try:
                    txt = data.decode("utf-8", errors="replace")
                except Exception:
                    txt = repr(data)
                for line in txt.splitlines()[:25]:
                    if line.strip():
                        print(f"      | {line}")
                break
        if not got_any:
            print("    未收到任何数据。可能原因：")
            print("      a) 固件没有向串口打印日志（OLED 只显示画面、不打日志很常见）")
            print("      b) 波特率不在探测列表内")
            print("      c) 端口被 Arduino/PlatformIO 的串口监视器占用（请先关闭）")

    print("\n" + "=" * 62)
    print("[3] 补充建议")
    print("=" * 62)
    print("""
  想确认「模组本身」是否正常（读芯片 ID / MAC / Flash 大小），用 esptool：
      esptool.py --port <端口> chip_id
      esptool.py --port <端口> flash_id
      esptool.py --port <端口> read_mac

  注意：esptool 需要进入下载模式，通常会把 EN 拉低，会中断当前运行的程序。
  若此时 OLED 正在显示画面，执行后需按一下板上的 EN/RST 键恢复。

  如果 OLED 在显示但串口完全没输出：这是正常现象 —— OLED 走 I2C/SPI，
  与串口日志是两条独立通道。要验证 OLED，需读取固件代码里 I2C 地址
  (常见 0x3C) 并确认 SSD1306/SH1106 驱动跑通。
""")


if __name__ == "__main__":
    main()
