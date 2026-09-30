# -*- coding: utf-8 -*-
"""
YY 屏幕遥控：手机通过 WiFi 网页按钮控制 ST7789 彩屏
  按钮：HELLO YY / 模拟时钟 / 机器人 / 息屏，还能用手机校准时钟

用法（二选一）：
  A. Thonny 打开本文件按 F5 运行（调试推荐）
  B. 开机自启：把本文件另存到板子上覆盖 main.py（原 main.py 已备份为 main_old.py）

网络：优先连家里路由器（下面 SSID/PASSWORD）；12 秒连不上会自动开热点
     热点名 YY-ESP32，密码 12345678。屏幕上会显示 IP 地址。
     ⚠ 本文件含 WiFi 明文密码，分享给别人前先删掉！
"""
import time
import math
import machine
import network
import socket
from machine import Pin, SPI

# ========================= 配置区 =========================
SSID     = "YOUR_WIFI_SSID"            # 家里路由器名（优先连接）
PASSWORD = "YOUR_WIFI_PASSWORD" # 路由器密码
AP_SSID  = "YY-ESP32"           # 备用热点名（路由器连不上时自动开）
AP_PASS  = "12345678"           # 热点密码（WPA2 要求至少 8 位）
TZ_OFFSET = 8 * 3600            # NTP 对时是 UTC，中国 +8 小时
PORT     = 80

# ================ 显示驱动（接线同 main.py） ================
# 屏: GND CS DC RES SDA SCL VCC BLK -> GND 5  2  4  23 18 3V3 19
SCK, MOSI, CS, DC, RST, BL = 18, 23, 5, 2, 4, 19
W = H = 240

spi = SPI(1, baudrate=20000000, polarity=0, phase=0,
          sck=Pin(SCK), mosi=Pin(MOSI))
cs  = Pin(CS,  Pin.OUT, value=1)
dc  = Pin(DC,  Pin.OUT, value=1)
rst = Pin(RST, Pin.OUT, value=1)
bl  = Pin(BL,  Pin.OUT, value=1)

# 常用色（RGB565，高字节先发——与已验证的 main.py 一致）
BLACK=0x0000; WHITE=0xFFFF; RED=0xF800; GREEN=0x07E0; BLUE=0x001F
YELLOW=0xFFE0; CYAN=0x07FF; GRAY=0x7BEF; ORANGE=0xFD20
SKY=0x65BE; AMBER=0xFE00


def cmd(c, data=None):
    dc.value(0); cs.value(0); spi.write(bytes((c,)))
    if data:
        dc.value(1); spi.write(data)
    cs.value(1)


def _init_screen():
    rst.value(0); time.sleep_ms(20); rst.value(1); time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)            # SWRESET
    cmd(0x11); time.sleep_ms(120)            # SLPOUT
    cmd(0x3A, b'\x55')                       # RGB565
    cmd(0x36, b'\x00')                       # MADCTL
    cmd(0xB2, b'\x0c\x0c\x00\x33\x33')
    cmd(0xB7, b'\x72')
    cmd(0xBB, b'\x3d')
    cmd(0xC0, b'\x2c')
    cmd(0xC2, b'\x01\xff')
    cmd(0xC3, b'\x19')
    cmd(0xC4, b'\x20')
    cmd(0xC6, b'\x0f')
    cmd(0xD0, b'\xa4\xa1')
    cmd(0xE0, b'\xd0\x04\x0d\x11\x13\x2b\x3f\x54\x4c\x18\x0d\x0b\x1f\x23')
    cmd(0xE1, b'\xd0\x04\x0c\x11\x13\x2c\x3f\x44\x51\x2f\x1f\x1f\x20\x23')
    cmd(0x21)                                # INVON（IPS 必开）
    cmd(0x29)                                # DISPON


_init_screen()

# ========================= 基础绘图 =========================

def _window(x, y, w, h):
    """设写入窗口，返回时 cs=0、dc=1，调用方写完像素须 cs.value(1)"""
    cmd(0x2A, bytes((0, x, 0, x + w - 1)))
    cmd(0x2B, bytes((0, y, 0, y + h - 1)))
    dc.value(0); cs.value(0); spi.write(b'\x2c'); dc.value(1)


def fill_rect(x, y, w, h, c):
    x = max(0, x); y = max(0, y)
    w = min(w, W - x); h = min(h, H - y)
    if w <= 0 or h <= 0:
        return
    row = bytes((c >> 8, c & 0xFF)) * w
    _window(x, y, w, h)
    for _ in range(h):
        spi.write(row)
    cs.value(1)


def hline(x, y, w, c): fill_rect(x, y, w, 1, c)
def vline(x, y, h, c): fill_rect(x, y, 1, h, c)


def pixel(x, y, c):
    if 0 <= x < W and 0 <= y < H:
        fill_rect(x, y, 1, 1, c)


def line(x0, y0, x1, y1, c):
    """Bresenham 直线"""
    dx = abs(x1 - x0); dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        pixel(x0, y0, c)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy: err += dy; x0 += sx
        if e2 <= dx: err += dx; y0 += sy


def circle(cx, cy, r, c):
    """中点圆"""
    x, y, err = r, 0, 1 - r
    while x >= y:
        for px, py in ((cx+x,cy+y),(cx+y,cy+x),(cx-y,cy+x),(cx-x,cy+y),
                       (cx-x,cy-y),(cx-y,cy-x),(cx+y,cy-x),(cx+x,cy-y)):
            pixel(px, py, c)
        y += 1
        if err < 0:
            err += 2 * y + 1
        else:
            x -= 1; err += 2 * (y - x) + 1


def disc(cx, cy, r, c):
    """实心圆：逐行算弦宽，比逐点画快得多"""
    for dy in range(-r, r + 1):
        half = int(round((r * r - dy * dy) ** 0.5))
        hline(cx - half, cy + dy, 2 * half + 1, c)


# 8x8 点阵字体（只嵌本项目用到的字符）
FONT = {
    '0':(0x3C,0x66,0x6E,0x76,0x66,0x66,0x3C,0x00),
    '1':(0x18,0x1C,0x18,0x18,0x18,0x18,0x7E,0x00),
    '2':(0x3C,0x66,0x06,0x0C,0x30,0x60,0x7E,0x00),
    '3':(0x3C,0x66,0x06,0x1C,0x06,0x66,0x3C,0x00),
    '4':(0x0C,0x1C,0x2C,0x4C,0x7E,0x0C,0x0C,0x00),
    '5':(0x7E,0x60,0x7C,0x06,0x06,0x66,0x3C,0x00),
    '6':(0x1C,0x30,0x60,0x7C,0x66,0x66,0x3C,0x00),
    '7':(0x7E,0x66,0x0C,0x18,0x18,0x18,0x18,0x00),
    '8':(0x3C,0x66,0x66,0x3C,0x66,0x66,0x3C,0x00),
    '9':(0x3C,0x66,0x66,0x3E,0x06,0x0C,0x38,0x00),
    ':':(0x00,0x18,0x18,0x00,0x18,0x18,0x00,0x00),
    '.':(0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00),
    ',':(0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x30),
    '%':(0x62,0x64,0x08,0x10,0x20,0x46,0x8C,0x00),
    '!':(0x18,0x18,0x18,0x18,0x18,0x00,0x18,0x00),
    '-':(0x00,0x00,0x00,0x00,0x7E,0x00,0x00,0x00),
    ' ':(0x00,)*8,
    'A':(0x18,0x3C,0x66,0x66,0x7E,0x66,0x66,0x00),
    'B':(0x7C,0x66,0x66,0x7C,0x66,0x66,0x7C,0x00),
    'C':(0x3C,0x66,0x60,0x60,0x60,0x66,0x3C,0x00),
    'D':(0x78,0x6C,0x66,0x66,0x66,0x6C,0x78,0x00),
    'E':(0x7E,0x60,0x60,0x78,0x60,0x60,0x7E,0x00),
    'F':(0x7E,0x60,0x60,0x78,0x60,0x60,0x60,0x00),
    'G':(0x3E,0x63,0x63,0x7F,0x03,0x63,0x3E,0x00),
    'Z':(0x7E,0x06,0x0C,0x18,0x30,0x60,0x7E,0x00),
    '/':(0x00,0x03,0x06,0x0C,0x18,0x30,0x40,0x00),
    'H':(0x66,0x66,0x66,0x7E,0x66,0x66,0x66,0x00),
    'I':(0x7E,0x18,0x18,0x18,0x18,0x18,0x7E,0x00),
    'J':(0x0C,0x0C,0x0C,0x0C,0x0C,0x6C,0x38,0x00),
    'Q':(0x3C,0x66,0x66,0x66,0x76,0x1C,0x0E,0x00),
    'V':(0x66,0x66,0x66,0x66,0x66,0x3C,0x18,0x00),
    'X':(0x66,0x66,0x3C,0x18,0x3C,0x66,0x66,0x00),
    'K':(0x66,0x6C,0x78,0x70,0x78,0x6C,0x66,0x00),
    'L':(0x60,0x60,0x60,0x60,0x60,0x60,0x7E,0x00),
    'M':(0x66,0x7F,0x7F,0x6B,0x63,0x63,0x63,0x00),
    'N':(0x66,0x6E,0x76,0x7E,0x7E,0x6E,0x66,0x00),
    'O':(0x3C,0x66,0x66,0x66,0x66,0x66,0x3C,0x00),
    'P':(0x7C,0x66,0x66,0x7C,0x60,0x60,0x60,0x00),
    'R':(0x7C,0x66,0x66,0x7C,0x78,0x6C,0x66,0x00),
    'S':(0x3C,0x66,0x60,0x3C,0x06,0x66,0x3C,0x00),
    'T':(0x7E,0x18,0x18,0x18,0x18,0x18,0x18,0x00),
    'U':(0x66,0x66,0x66,0x66,0x66,0x66,0x3C,0x00),
    'W':(0x63,0x63,0x63,0x6B,0x7F,0x77,0x63,0x00),
    'Y':(0x66,0x66,0x66,0x3C,0x18,0x18,0x18,0x00),
    'a':(0x00,0x00,0x70,0x08,0x78,0x88,0x78,0x00),
    'b':(0x00,0x80,0xF0,0x88,0x88,0xF0,0x00,0x00),
    'c':(0x00,0x00,0x70,0x88,0x80,0x88,0x78,0x00),
    'd':(0x00,0x08,0x68,0x98,0x98,0x68,0x00,0x00),
    'e':(0x00,0x00,0x70,0x88,0xF8,0x80,0x70,0x00),
    'f':(0x00,0x30,0x48,0x70,0x48,0x48,0x00,0x00),
    'g':(0x00,0x00,0x78,0x88,0x88,0x78,0x08,0x70),
    'h':(0x00,0x80,0xF0,0x88,0x88,0x88,0x00,0x00),
    'i':(0x00,0x40,0x00,0x40,0x40,0x40,0x40,0x00),
    'j':(0x00,0x10,0x00,0x10,0x10,0x10,0x90,0x60),
    'k':(0x00,0x80,0x90,0xA0,0xC0,0xA0,0x00,0x00),
    'l':(0x40,0x40,0x40,0x40,0x40,0x40,0x30,0x00),
    'm':(0x00,0x00,0xD8,0xA8,0xA8,0xA8,0x00,0x00),
    'n':(0x00,0x00,0xF0,0x88,0x88,0x88,0x00,0x00),
    'o':(0x00,0x00,0x70,0x88,0x88,0x88,0x70,0x00),
    'p':(0x00,0x00,0xF0,0x88,0x88,0xF0,0x80,0x80),
    'q':(0x00,0x00,0x68,0x98,0x98,0x78,0x08,0x08),
    'r':(0x00,0x00,0x70,0x80,0x80,0x80,0x00,0x00),
    's':(0x00,0x00,0x78,0x80,0x70,0x08,0xF0,0x00),
    't':(0x00,0x40,0xE0,0x40,0x40,0x30,0x00,0x00),
    'u':(0x00,0x00,0x88,0x88,0x88,0x98,0x68,0x00),
    'v':(0x00,0x00,0x88,0x88,0x88,0x50,0x20,0x00),
    'w':(0x00,0x00,0x88,0x88,0xA8,0xA8,0x50,0x00),
    'x':(0x00,0x00,0x88,0x50,0x20,0x50,0x88,0x00),
    'y':(0x00,0x00,0x88,0x88,0x88,0x78,0x08,0x70),
    'z':(0x00,0x00,0xF8,0x20,0x40,0x80,0xF8,0x00),
}


def draw_text(x, y, s, text, fg, bg=None):
    """画一行字。按"横向连续点亮段"整段填色（比逐点快得多）。
    未收录的字符画空心方框，一眼能发现缺字。"""
    cx = x
    for ch in text:
        g = FONT.get(ch)
        if bg is not None:
            fill_rect(cx, y, 8 * s, 8 * s, bg)
        if g:
            for r in range(8):
                bits, col = g[r], 0
                while col < 8:
                    if (bits >> (7 - col)) & 1:
                        run = 1
                        while (col + run < 8 and
                               (bits >> (7 - col - run)) & 1):
                            run += 1
                        fill_rect(cx + col * s, y + r * s, run * s, s, fg)
                        col += run
                    else:
                        col += 1
        else:
            hline(cx, y, 8 * s, fg)
            hline(cx, y + 8 * s - 1, 8 * s, fg)
            vline(cx, y, 8 * s, fg)
            vline(cx + 8 * s - 1, y, 8 * s, fg)
        cx += 8 * s


def text_center(y, s, text, fg, bg=None):
    while s > 1 and 8 * s * len(text) > W:   # 太宽自动缩小字号（防呆）
        s -= 1
    draw_text(max(0, (W - 8 * s * len(text)) // 2), y, s, text, fg, bg)

# ========================= 三个画面 =========================

def screen_hello():
    fill_rect(0, 0, W, H, BLUE)
    text_center(44, 4, 'HELLO,', WHITE)
    text_center(96, 4, 'YangYang!', YELLOW)
    # 一颗小爱心
    circle(108, 178, 11, RED); circle(132, 178, 11, RED)
    for dy in range(21):
        half = 21 - dy
        hline(120 - half, 180 + dy, half * 2, RED)
    text_center(214, 1, 'FROM YOUR PHONE', CYAN)


def screen_robot():
    fill_rect(0, 0, W, H, BLACK)
    vline(120, 22, 14, GRAY)                    # 天线
    circle(120, 17, 5, RED)
    fill_rect(68, 38, 104, 74, SKY)             # 头
    line(68, 38, 172, 38, WHITE); line(68, 111, 172, 111, WHITE)
    line(68, 38, 68, 111, WHITE); line(172, 38, 172, 111, WHITE)
    fill_rect(58, 62, 10, 26, AMBER)            # 耳朵
    fill_rect(172, 62, 10, 26, AMBER)
    fill_rect(86, 58, 18, 20, WHITE)            # 眼睛
    fill_rect(136, 58, 18, 20, WHITE)
    fill_rect(92, 64, 6, 10, BLACK)
    fill_rect(142, 64, 6, 10, BLACK)
    fill_rect(102, 92, 36, 5, WHITE)            # 嘴
    fill_rect(110, 112, 20, 8, GRAY)            # 脖子
    fill_rect(62, 120, 116, 68, SKY)            # 身体
    fill_rect(86, 132, 68, 40, BLACK)           # 胸口面板
    circle(120, 152, 12, AMBER)
    fill_rect(116, 148, 8, 8, RED)
    fill_rect(40, 126, 16, 48, GRAY)            # 手臂
    fill_rect(184, 126, 16, 48, GRAY)
    circle(48, 180, 8, AMBER); circle(192, 180, 8, AMBER)
    fill_rect(86, 188, 26, 28, GRAY)            # 腿
    fill_rect(128, 188, 26, 28, GRAY)
    fill_rect(78, 216, 40, 10, WHITE)           # 脚
    fill_rect(122, 216, 40, 10, WHITE)

# ---- 模拟时钟 ----
CX, CY = 120, 105
_old_hands = None


def _tick(i, r1, r2, c):
    a = i * 30 * math.pi / 180
    line(CX + int(r1 * math.sin(a)), CY - int(r1 * math.cos(a)),
         CX + int(r2 * math.sin(a)), CY - int(r2 * math.cos(a)), c)


def _hand(angle_deg, length, c, width=1):
    a = angle_deg * math.pi / 180
    x2 = CX + int(length * math.sin(a))
    y2 = CY - int(length * math.cos(a))
    for i in range(width):
        line(CX, CY, x2 + i, y2, c)


def screen_clock():
    global _old_hands
    fill_rect(0, 0, W, H, BLACK)
    circle(CX, CY, 92, GRAY)
    for i in range(12):
        _tick(i, 92, 80 if i % 3 == 0 else 86, WHITE)
    _old_hands = None
    clock_update(time.localtime(time.time() + TZOFF))


def clock_update(t):
    global _old_hands
    h, m, s = t[3], t[4], t[5]
    if _old_hands:                       # 先擦掉旧指针
        for ang, ln, wd in _old_hands:
            _hand(ang, ln, BLACK, wd)
        for i in range(12):              # 补回被擦到的刻度
            _tick(i, 92, 80 if i % 3 == 0 else 86, WHITE)
    hh = (h % 12) * 30 + m * 0.5
    mm = m * 6 + s * 0.1
    ss = s * 6
    _hand(hh, 46, WHITE, 3)
    _hand(mm, 66, YELLOW, 2)
    _hand(ss, 78, RED, 1)
    circle(CX, CY, 4, YELLOW)
    _old_hands = [(hh, 46, 3), (mm, 66, 2), (ss, 78, 1)]
    text_center(206, 2, '%02d:%02d:%02d' % (h, m, s), CYAN, BLACK)

# ---- 上海天气（Open-Meteo 免费接口，无需 key） ----
WX = None            # 最近一次天气缓存 {temp,wind,code,hi,lo}
WX_AT = 0            # 上次成功获取的时刻
WX_ERR = False       # 上次获取是否失败
WX_INTERVAL = 600    # 成功后每 10 分钟刷新
NETMODE = 'sta'      # 'sta'=路由器(有外网) / 'ap'=热点(无外网)


def fetch_weather():
    """HTTP/1.0 直连 Open-Meteo（响应非 chunked，读关闭即完整）"""
    import usocket as s
    import json
    path = ("/v1/forecast?latitude=31.23&longitude=121.47"
            "&current_weather=true&daily=temperature_2m_max,temperature_2m_min"
            "&timezone=Asia%2FShanghai&forecast_days=1")
    addr = s.getaddrinfo('api.open-meteo.com', 80)[0][-1]
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)
    sock.settimeout(6)
    try:
        sock.connect(addr)
        sock.send(('GET %s HTTP/1.0\r\nHost: api.open-meteo.com\r\n'
                   'User-Agent: ESP32-YY\r\n\r\n' % path).encode())
        buf = b''
        while len(buf) < 6000:
            try:
                d = sock.recv(512)
            except OSError:
                break
            if not d:
                break
            buf += d
    finally:
        sock.close()
    body = buf.split(b'\r\n\r\n', 1)[1]
    j = json.loads(body)
    cur = j['current_weather']
    return {'temp': round(cur['temperature']),
            'wind': round(cur['windspeed']),
            'code': cur['weathercode'],
            'hi': round(j['daily']['temperature_2m_max'][0]),
            'lo': round(j['daily']['temperature_2m_min'][0])}


def wmo(code):
    """WMO 天气码 -> (网页中文, 屏幕英文, 图标)"""
    if code == 0:
        return ('晴', 'SUNNY', 'sun')
    if code in (1, 2):
        return ('多云', 'PARTLY', 'psun')
    if code == 3:
        return ('阴', 'CLOUDY', 'cloud')
    if code in (45, 48):
        return ('雾', 'FOG', 'fog')
    if code in (51, 53, 55, 56, 57):
        return ('毛毛雨', 'DRIZZLE', 'rain')
    if code in (61, 63, 65, 66, 67):
        return ('雨', 'RAIN', 'rain')
    if code in (71, 73, 75, 77, 85, 86):
        return ('雪', 'SNOW', 'snow')
    if code in (80, 81, 82):
        return ('阵雨', 'SHOWERS', 'rain')
    if code in (95, 96, 99):
        return ('雷阵雨', 'STORM', 'storm')
    return ('天气', 'W-%d' % code, 'cloud')


def _cloud(cx, cy, c=WHITE):
    disc(cx - 15, cy, 12, c)
    disc(cx + 15, cy, 12, c)
    disc(cx, cy - 8, 16, c)
    fill_rect(cx - 26, cy, 52, 13, c)


def _sun_rays(cx, cy, r, c):
    for i in range(8):
        a = i * 45 * math.pi / 180
        line(cx + int((r + 4) * math.cos(a)), cy + int((r + 4) * math.sin(a)),
             cx + int((r + 12) * math.cos(a)), cy + int((r + 12) * math.sin(a)), c)


def _draw_icon(kind, cx, cy):
    if kind == 'sun':
        disc(cx, cy, 16, YELLOW)
        _sun_rays(cx, cy, 16, YELLOW)
    elif kind == 'psun':
        disc(cx + 20, cy - 18, 9, YELLOW)
        _sun_rays(cx + 20, cy - 18, 9, YELLOW)
        _cloud(cx - 4, cy + 6)
    elif kind == 'cloud':
        _cloud(cx, cy, GRAY)
    elif kind == 'rain':
        _cloud(cx, cy - 6)
        for dx in (-14, 0, 14):
            line(cx + dx, cy + 16, cx + dx - 5, cy + 32, CYAN)
    elif kind == 'snow':
        _cloud(cx, cy - 6)
        for dx, dy in ((-14, 22), (0, 26), (14, 22), (-7, 34), (7, 34)):
            disc(cx + dx, cy + dy, 2, WHITE)
    elif kind == 'storm':
        _cloud(cx, cy - 8, GRAY)
        line(cx + 8, cy + 8, cx - 4, cy + 22, YELLOW)
        line(cx - 4, cy + 22, cx + 4, cy + 22, YELLOW)
        line(cx + 4, cy + 22, cx - 8, cy + 38, YELLOW)
    elif kind == 'fog':
        for i, (dy, w) in enumerate(((-10, 60), (0, 76), (10, 52), (20, 68))):
            hline(cx - w // 2, cy + dy, w, GRAY)


def screen_weather():
    fill_rect(0, 0, W, H, BLACK)
    text_center(10, 2, 'SHANGHAI', CYAN, BLACK)
    if WX is None:
        if NETMODE != 'sta':
            text_center(96, 2, 'NO INTERNET', ORANGE, BLACK)
            text_center(124, 1, 'WEATHER NEEDS WIFI', GRAY, BLACK)
        elif WX_ERR:
            text_center(96, 2, 'NO LINK', ORANGE, BLACK)
            text_center(124, 1, 'RETRY LATER', GRAY, BLACK)
        else:
            text_center(96, 2, 'LOADING...', GRAY, BLACK)
        return
    zh, en, icon = wmo(WX['code'])
    _draw_icon(icon, 120, 64)
    tstr = str(WX['temp'])
    wd = len(tstr) * 8 * 5
    x0 = (W - (wd + 30)) // 2
    draw_text(x0, 112, 5, tstr, WHITE)
    disc(x0 + wd + 8, 116, 4, WHITE)          # 度符号
    draw_text(x0 + wd + 16, 118, 3, 'C', YELLOW)
    text_center(160, 2, en, CYAN, BLACK)
    text_center(186, 2, 'HI %d LO %d' % (WX['hi'], WX['lo']), AMBER, BLACK)
    t = time.localtime(time.time() + TZOFF)
    text_center(216, 1, 'WIND %dKM/H  UPD %02d:%02d' % (WX['wind'], t[3], t[4]),
                GRAY, BLACK)


def do_weather_refresh():
    """获取天气并重画（失败不打断主循环）"""
    global WX, WX_AT, WX_ERR
    if NETMODE != 'sta':
        return
    print('天气：正在获取上海天气...')
    try:
        data = fetch_weather()
        WX = data
        WX_AT = time.time()
        WX_ERR = False
        print('WX: %dC code=%d wind=%dkm/h hi=%d lo=%d'
              % (data['temp'], data['code'], data['wind'], data['hi'], data['lo']))
        if MODE == 'weather':
            screen_weather()
    except Exception as e:
        WX_ERR = True
        WX_AT = time.time() - WX_INTERVAL + 60   # 失败 60 秒后重试
        print('天气获取失败:', e)
        if MODE == 'weather' and WX is None:
            screen_weather()


# ========================= 网络 =========================

def _ntp_utc():
    """手动 NTP 查询（自带超时，不依赖 ntptime 模块），返回 UTC epoch"""
    import usocket as s
    addr = s.getaddrinfo("ntp.aliyun.com", 123)[0][-1]
    sock = s.socket(s.AF_INET, s.SOCK_DGRAM)
    sock.settimeout(3)
    try:
        sock.sendto(b"\x1b" + 47 * b"\0", addr)
        msg = sock.recv(48)
        return int.from_bytes(msg[40:48], "big") - 2208988800
    finally:
        sock.close()


def wifi_connect():
    """返回 (ip, tz偏移)。先连路由器，失败开热点"""
    sta = network.WLAN(network.STA_IF)
    sta.active(True)
    print('正在连接路由器 %s ...' % SSID)
    sta.connect(SSID, PASSWORD)
    t0 = time.time()
    while time.time() - t0 < 12 and not sta.isconnected():
        time.sleep(0.5)
    if sta.isconnected():
        global NETMODE, NET_IP, NET_MASK
        NETMODE = 'sta'
        ifc = sta.ifconfig()
        ip = ifc[0]
        NET_IP = ifc[0]
        NET_MASK = ifc[1]
        print('路由器连接成功, IP = %s' % ip)
        try:
            utc = _ntp_utc()
            t = time.localtime(utc)
            machine.RTC().datetime((t[0], t[1], t[2], t[3], t[4], t[5], 0, 0))
            print('NTP 对时成功（UTC+8 已应用）')
            return ip, TZ_OFFSET
        except Exception as e:
            print('NTP 对时失败（不影响，可用手机校时）:', e)
            return ip, 0
    print('路由器连不上，自动开启热点 %s' % AP_SSID)
    global NETMODE, NET_IP, NET_MASK
    NETMODE = 'ap'
    ap = network.WLAN(network.AP_IF)
    ap.config(essid=AP_SSID, password=AP_PASS)
    ap.active(True)
    t0 = time.time()
    while not ap.active() and time.time() - t0 < 10:
        time.sleep(0.3)
    ifc = ap.ifconfig()
    ip = ifc[0]
    NET_IP = ifc[0]
    NET_MASK = ifc[1]
    print('热点已开启, 手机连 %s（密码 %s）后访问 http://%s/' % (AP_SSID, AP_PASS, ip))
    return ip, 0

# ========================= HTTP 服务 =========================
_PAGE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>YY 屏幕遥控</title><style>
body{font-family:sans-serif;background:#0f172a;color:#e2e8f0;text-align:center;margin:0;padding:22px}
h1{font-size:26px;margin:6px 0 2px}.ip{color:#93c5fd;margin:0 0 4px;font-size:14px}
.wx{color:#fbbf24;margin:0 0 14px;font-size:15px}
a.btn{display:block;margin:12px auto;padding:18px;border-radius:14px;font-size:21px;
text-decoration:none;color:#fff;max-width:330px}
a.on{outline:4px solid #fbbf24}
.b1{background:#2563eb}.b2{background:#059669}.b3{background:#7c3aed}.b4{background:#475569}
form{margin-top:20px;color:#94a3b8;font-size:15px}
input[type=time]{font-size:18px;padding:5px;border-radius:8px;border:none}
button{font-size:16px;padding:8px 14px;margin-left:6px;border-radius:8px;border:none;
background:#2563eb;color:#fff}
.tiny{font-size:12px;color:#64748b;margin-top:24px}</style></head><body>
<h1>YY 屏幕遥控</h1><p class="ip">开发板在线 · 当前：__MODE__</p><p class="wx">__WX__</p>
<a class="btn b1 __A__" href="/?mode=hello">显示 HELLO YY</a>
<a class="btn b2 __B__" href="/?mode=clock">模拟时钟</a>
<a class="btn b3 __C__" href="/?mode=robot">机器人</a>
<a class="btn b5 __E__" href="/?mode=weather">上海天气</a>
<a class="btn b4 __D__" href="/?mode=off">息屏</a>
<form>校准时钟：<input type="time" name="t"><input type="hidden" name="set" value="1">
<button type="submit">同步到开发板</button></form>
<p class="tiny">ESP32 · MicroPython · ST7789 240x240 · 天气数据 Open-Meteo</p></body></html>"""
_HEAD = ("HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
         "Connection: close\r\n\r\n")

MODE = 'hello'
IP = '0.0.0.0'
NET_IP = '0.0.0.0'          # 板子本机 IP（wifi_connect 里填）
NET_MASK = '255.255.255.0'  # 子网掩码（同上）
TZOFF = TZ_OFFSET


def same_subnet(peer_ip):
    """访问控制：只允许与板子同一网段的客户端（按子网掩码逐字节判断）"""
    try:
        a = bytes(int(x) for x in peer_ip.split('.'))
        b = bytes(int(x) for x in NET_IP.split('.'))
        m = bytes(int(x) for x in NET_MASK.split('.'))
        for i in range(4):
            if (a[i] & m[i]) != (b[i] & m[i]):
                return False
        return True
    except Exception:
        return False


def _page(mode):
    p = _PAGE.replace('__MODE__', {'hello': 'HELLO YY', 'clock': '模拟时钟',
                                   'robot': '机器人', 'weather': '上海天气',
                                   'off': '息屏'}.get(mode, mode))
    if WX:
        p = p.replace('__WX__', '上海 %d°C %s · 风 %dkm/h'
                      % (WX['temp'], wmo(WX['code'])[0], WX['wind']))
    else:
        p = p.replace('__WX__', '')
    p = p.replace('__A__', 'on' if mode == 'hello' else '')
    p = p.replace('__B__', 'on' if mode == 'clock' else '')
    p = p.replace('__C__', 'on' if mode == 'robot' else '')
    p = p.replace('__E__', 'on' if mode == 'weather' else '')
    p = p.replace('__D__', 'on' if mode == 'off' else '')
    return p


def set_mode(m):
    global MODE
    MODE = m
    print('MODE ->', m.upper())
    if m == 'off':
        fill_rect(0, 0, W, H, BLACK)
        bl.value(0)
        return
    bl.value(1)
    if m == 'hello':
        screen_hello()
    elif m == 'robot':
        screen_robot()
    elif m == 'clock':
        screen_clock()
    elif m == 'weather':
        screen_weather()


def handle(conn):
    try:
        conn.settimeout(2)
        req = conn.recv(400)
        if not req:
            return
        first = req.decode('utf-8', 'ignore').split('\r\n')[0]
        if 'favicon' in first:
            return
        global TZOFF
        mode = MODE
        if '?' in first:
            q = first.split('?')[1].split(' ')[0]
            params = {}
            for kv in q.split('&'):
                if '=' in kv:
                    k, v = kv.split('=', 1)
                    params[k] = v
            if params.get('set') == '1' and 't' in params:
                try:                      # 手机校时 HH:MM
                    hh, mm = params['t'].split(':')
                    machine.RTC().datetime((2026, 1, 1, int(hh), int(mm), 0, 0, 0))
                    TZOFF = 0
                    print('手机校时 -> %02d:%02d' % (int(hh), int(mm)))
                    mode = 'clock'
                except Exception:
                    pass
            if params.get('mode') in ('hello', 'clock', 'robot', 'weather', 'off'):
                mode = params['mode']
        if mode != MODE:
            set_mode(mode)
        conn.send(_HEAD)
        conn.send(_page(MODE))
    except Exception as e:
        print('请求处理出错:', e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def main():
    global IP, TZOFF
    ip, tz = wifi_connect()
    IP = ip
    TZOFF = tz
    # 开机画面：显示连接信息（学生/手机照着屏幕输 IP）
    fill_rect(0, 0, W, H, BLACK)
    text_center(24, 3, 'YY REMOTE', CYAN)
    if sta_connected():
        text_center(78, 2, 'WIFI:' + SSID, GRAY)
    else:
        text_center(78, 2, 'AP:' + AP_SSID, GRAY)
    text_center(106, 2, 'IP:' + ip, WHITE)
    text_center(150, 1, 'CONNECT PHONE AND OPEN', GRAY)
    text_center(162, 1, 'THE ADDRESS ABOVE', GRAY)
    time.sleep(3)
    set_mode('hello')

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((NET_IP, PORT))          # 只绑本机网卡 IP（不绑 0.0.0.0）
    srv.listen(2)
    srv.settimeout(0.3)
    print('Web 服务就绪: http://%s/  （按 Ctrl+C 退出）' % ip)
    print('访问控制: 仅同网段 %s/%s 内的设备可控制'
          % (NET_IP, NET_MASK))

    last = -1
    try:
        while True:
            try:
                conn, addr = srv.accept()
            except OSError:
                conn = None
            if conn:
                if same_subnet(addr[0]):
                    handle(conn)
                else:
                    # 安全红线：跨网段/外网来源一律拒绝
                    print('拒绝非局域网访问:', addr[0])
                    try:
                        conn.close()
                    except Exception:
                        pass
            if MODE == 'weather' and NETMODE == 'sta':
                if WX is None or time.time() - WX_AT > WX_INTERVAL:
                    do_weather_refresh()
            if MODE == 'clock':
                t = time.localtime(time.time() + TZOFF)
                if t[5] != last:
                    clock_update(t)
                    last = t[5]
    except KeyboardInterrupt:
        print('已停止，REPL 交还。')


def sta_connected():
    return network.WLAN(network.STA_IF).isconnected()


if __name__ == '__main__':
    main()
