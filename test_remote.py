#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
上传 web_screen_remote.py 到开发板并分阶段实测：
  [1] 分块上传（raw REPL 写文件） + 字节数校验
  [2] import 模块（语法/驱动检查）
  [3] 三个画面逐个绘制（串口看有没有 Traceback）
  [4] 启动 main()（WiFi + Web 服务），抓 IP
  [5] 若为局域网 IP，从电脑直接 HTTP 请求各模式（端到端验证）
  [6] Ctrl+C 停止，复位板子恢复原 main.py 演示
"""
import os
import re
import sys
import time
import serial
import urllib.request

PORT = "COM3"
BAUD = 115200
SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web_screen_remote.py")
DST = "web_screen_remote.py"

ser = serial.Serial(PORT, BAUD, timeout=0.2)


def drain(t=0.3):
    time.sleep(t)
    out = bytearray()
    while ser.in_waiting:
        out.extend(ser.read(ser.in_waiting))
    return bytes(out)


def board_reset():
    ser.dtr = False; ser.rts = True
    time.sleep(0.15)
    ser.rts = False
    drain(6.0)


def _enter_raw(attempts=3):
    """Ctrl+A 进入 raw REPL 并验证回显标志，失败重试。
    注意：Ctrl+E 是 paste mode（会回显代码），raw REPL 必须用 Ctrl+A。"""
    for i in range(attempts):
        ser.write(b"\x03\x03"); time.sleep(0.3); drain(0.1)
        ser.reset_input_buffer()
        ser.write(b"\x01")
        time.sleep(0.5)
        r = drain(0.2)
        if b"raw REPL" in r:
            ser.reset_input_buffer()
            return True
        print("  [raw 模式进入失败 第%d次] 回显: %r" % (i + 1, r[:120]))
        time.sleep(0.5)
    return False


def raw_exec(code, wait=8.0, expect_finish=True):
    """raw REPL 执行一段代码，返回 (输出, 是否执行完毕)"""
    if not _enter_raw():
        raise RuntimeError("无法进入 raw REPL 模式")
    data = code.encode()
    for i in range(0, len(data), 48):
        ser.write(data[i:i + 48])
        time.sleep(0.03)
    time.sleep(0.2)
    ser.write(b"\x04")
    buf, t0, done = bytearray(), time.time(), False
    while time.time() - t0 < wait:
        n = ser.in_waiting
        if n:
            buf.extend(ser.read(n))
        if b"\x04" in buf:      # raw REPL 执行完输出末尾是 0x04
            done = True
            break
        time.sleep(0.03)
    ser.write(b"\x02"); time.sleep(0.2); drain(0.1)
    return buf.decode("utf-8", "replace"), done


def upload():
    with open(SRC, "rb") as f:
        content = f.read()
    text = content.decode("utf-8")
    raw_exec("import os\ntry:\n    os.remove('%s')\nexcept OSError:\n    pass" % DST, 4)
    chunk, chunks = "", []
    for line in text.splitlines(keepends=True):
        chunk += line
        if len(chunk) >= 500:
            chunks.append(chunk); chunk = ""
    if chunk:
        chunks.append(chunk)
    t0 = time.time()
    for i, c in enumerate(chunks):
        code = "f=open('%s','%s');f.write(%r);f.close()" % (DST, "w" if i == 0 else "a", c)
        out, done = raw_exec(code, 6)
        if not done or "Traceback" in out:
            print("[上传失败] chunk %d/%d: %s" % (i + 1, len(chunks), out[:300]))
            return None
    print("[上传] %d 块全部写入，用时 %.1fs" % (len(chunks), time.time() - t0))
    out, _ = raw_exec("print(os.stat('%s')[6])" % DST, 4)
    m = re.search(r"(\d+)", out)
    size = int(m.group(1)) if m else -1
    ok = size == len(content)
    print("[校验] 板上 %d 字节 / PC %d 字节 -> %s" % (size, len(content), "一致" if ok else "不一致!"))
    return size if ok else None


def main():
    print("=== 复位板子（原 main.py 先跑一遍）===")
    board_reset()

    print("\n=== [1-2] 上传 + import 检查 ===")
    if upload() is None:
        sys.exit(1)
    out, done = raw_exec("import web_screen_remote; print('IMPORT_OK')", 15)
    if "IMPORT_OK" not in out or "Traceback" in out:
        print("[import 失败]\n", out[-800:]); sys.exit(1)
    print("[import] OK")

    print("\n=== [2.5] 局域网访问控制·单元测试 ===")
    out, done = raw_exec(
        "web_screen_remote.NET_IP = '192.168.71.85'\n"
        "web_screen_remote.NET_MASK = '255.255.255.0'\n"
        "print('SUBNET',"
        " web_screen_remote.same_subnet('192.168.71.9'),"
        " web_screen_remote.same_subnet('192.168.4.5'),"
        " web_screen_remote.same_subnet('8.8.8.8'),"
        " web_screen_remote.same_subnet('192.168.72.20'))", 8)
    ok_subnet = "SUBNET True False False False" in out
    print("[网段校验] 同段放行/跨段拒绝: %s" % ("OK" if ok_subnet else "FAIL: " + out[-250:]))
    if not ok_subnet:
        sys.exit(1)

    print("\n=== [3] 画面绘制测试 ===")
    for fn in ("screen_hello", "screen_robot", "screen_clock", "screen_weather"):
        out, done = raw_exec("web_screen_remote.%s(); print('DRAW_OK')" % fn, 20)
        bad = "Traceback" in out
        print("  %-14s %s" % (fn, "FAIL: " + out[-400:] if bad else "OK" if "DRAW_OK" in out else "超时"))
        if bad:
            sys.exit(1)

    print("\n=== [4] 启动 main()（WiFi + Web 服务，监听 20 秒）===")
    ser.write(b"\x03\x03"); time.sleep(0.2); ser.reset_input_buffer()
    ser.write(b"\x05"); time.sleep(0.4); drain(0.1)
    code = "web_screen_remote.main()"
    for i in range(0, len(code), 48):
        ser.write(code[i:i + 48].encode()); time.sleep(0.03)
    ser.write(b"\x04")
    buf, t0 = bytearray(), time.time()
    while time.time() - t0 < 20:
        if ser.in_waiting:
            buf.extend(ser.read(ser.in_waiting))
        time.sleep(0.05)
    log = buf.decode("utf-8", "replace")
    print(log[-1200:])
    m = re.search(r"http://(\d+\.\d+\.\d+\.\d+)/", log)
    if not m:
        print("[失败] 没抓到 IP"); sys.exit(1)
    ip = m.group(1)
    lan = not ip.startswith("192.168.4.")

    if lan:
        print("\n=== [5] 电脑直连 HTTP 端到端测试 (%s) ===" % ip)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        base = "http://%s" % ip
        for qs in ("?mode=clock", "?mode=robot", "?mode=weather", "?mode=hello", "/"):
            try:
                r = opener.open(base + qs, timeout=10)
                body = r.read()
                tag = "OK" if (qs == "/" or b"btn" in body) else "内容异常"
                print("  GET /%-13s -> %d 字节 %s" % (qs + "}", len(body), tag))
            except Exception as e:
                print("  GET /%-13s -> 失败: %s" % (qs + "}", e))
            time.sleep(9 if "weather" in qs else 2.5)   # 天气模式留出 API 抓取时间
    else:
        print("\n=== [5] 热点模式（192.168.4.x），电脑不在该网络，跳过 HTTP 直连 ===")
        print("  请用手机连热点 %s 后访问 http://%s/ 验证" % (
            re.search(r"热点已开启, 手机连 (\S+)", log).group(1) if re.search(r"热点已开启", log) else "YY-ESP32", ip))

    print("\n=== 串口模式切换日志（尾部）===")
    time.sleep(1)
    tail = drain(1.0).decode("utf-8", "replace")
    print(tail[-500:] if tail.strip() else "  (无)")

    print("\n=== [6] Ctrl+C 停止 + 复位还原 ===")
    ser.write(b"\x03\x03"); time.sleep(0.5)
    out = drain(2.0).decode("utf-8", "replace")
    print("  停止输出:", (out.strip().splitlines() or ["(无)"])[-1])
    board_reset()
    print("  板子已复位，原 main.py 演示恢复")
    ser.close()
    print("\n全部完成。")


if __name__ == "__main__":
    main()
