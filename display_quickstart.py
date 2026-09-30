# display_quickstart.py
# WLK1501SPI-8P (ST7789, 240x240) + ESP32  最小可复用驱动
#
# 接线（屏幕丝印顺序 GND CS DC RES SDA SCL VCC BLK）:
#   GND -> GND      CS  -> GPIO5     DC  -> GPIO2    RES -> GPIO4
#   SDA -> GPIO23   SCL -> GPIO18    VCC -> 3.3V     BLK -> GPIO19
#
# 注意:
#   1) 丝印 SDA/SCL 是 SPI 的 MOSI/SCK，不是 I2C。
#   2) 八针模块未引出 MISO，屏幕只写不读，不要调用 spi.read()。
#   3) SPI 速率不要超过 20MHz，40MHz 会让芯片崩溃重启。
#   4) 本屏 rowstart=0，窗口就是 0-239，不需要行偏移。
#
# 用法: 把本文件传到板子后
#   import display_quickstart as d
#   d.init(); d.fill(d.BLUE); d.text('Hello', 40, 110)

from machine import Pin, SPI
import time
import framebuf

# ---------- 引脚与尺寸 ----------
SCK, MOSI, CS, DC, RST, BL = 18, 23, 5, 2, 4, 19
WIDTH, HEIGHT = 240, 240

# ---------- 常用颜色 (RGB565) ----------
BLACK, WHITE = 0x0000, 0xFFFF
RED, GREEN, BLUE = 0xF800, 0x07E0, 0x001F
YELLOW, CYAN, MAGENTA = 0xFFE0, 0x07FF, 0xF81F

spi = SPI(1, baudrate=20000000, polarity=0, phase=0,
          sck=Pin(SCK), mosi=Pin(MOSI))
cs = Pin(CS, Pin.OUT, value=1)
dc = Pin(DC, Pin.OUT, value=1)
rst = Pin(RST, Pin.OUT, value=1)
bl = Pin(BL, Pin.OUT, value=1)


def cmd(c, data=None):
    dc.value(0)
    cs.value(0)
    spi.write(bytes([c]))
    if data is not None:
        dc.value(1)
        spi.write(data)
    cs.value(1)


def init():
    rst.value(0)
    time.sleep_ms(20)
    rst.value(1)
    time.sleep_ms(150)
    cmd(0x01); time.sleep_ms(150)   # SWRESET
    cmd(0x11); time.sleep_ms(120)   # SLPOUT
    cmd(0x3A, b'\x55')              # COLMOD RGB565
    cmd(0x36, b'\x00')              # MADCTL
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
    cmd(0x21)                       # INVON (IPS 屏必须开)
    cmd(0x29)                       # DISPON


def window(x0, y0, x1, y1):
    cmd(0x2A, bytes([x0 >> 8, x0 & 0xff, x1 >> 8, x1 & 0xff]))
    cmd(0x2B, bytes([y0 >> 8, y0 & 0xff, y1 >> 8, y1 & 0xff]))
    cmd(0x2C)


def backlight(on=True):
    bl.value(1 if on else 0)


def fill(color, x0=0, y0=0, x1=None, y1=None):
    x1 = WIDTH - 1 if x1 is None else x1
    y1 = HEIGHT - 1 if y1 is None else y1
    w = x1 - x0 + 1
    window(x0, y0, x1, y1)
    row = bytes([color >> 8, color & 0xff]) * w
    dc.value(1)
    cs.value(0)
    for _ in range(y1 - y0 + 1):
        spi.write(row)
    cs.value(1)


def fill_rect(x, y, w, h, color):
    fill(color, x, y, x + w - 1, y + h - 1)


def text(s, x, y, fg=WHITE, bg=BLACK, scale=2):
    """8x8 内置字体，scale 为放大倍数。文字区域按 bg 铺底。"""
    tw = len(s) * 8
    w_px, h_px = tw * scale, 8 * scale
    buf = bytearray(tw)
    fb = framebuf.FrameBuffer(buf, tw, 8, framebuf.MONO_HLSB)
    fb.text(s, 0, 0, 1)
    window(x, y, x + w_px - 1, y + h_px - 1)
    row = bytearray(w_px * 2)
    fhi, flo = fg >> 8, fg & 0xff
    bhi, blo = bg >> 8, bg & 0xff
    dc.value(1)
    cs.value(0)
    for r in range(h_px):
        src = r // scale
        for i in range(tw):
            on = fb.pixel(i, src)
            hi, lo = (fhi, flo) if on else (bhi, blo)
            for k in range(scale):
                j = i * scale + k
                row[2 * j] = hi
                row[2 * j + 1] = lo
        spi.write(row)
    cs.value(1)


def center_text(s, fg=WHITE, bg=BLACK, scale=2):
    tw = len(s) * 8 * scale
    text(s, max(0, (WIDTH - tw) // 2), (HEIGHT - 8 * scale) // 2, fg, bg, scale)


def demo():
    init()
    backlight(True)
    fill(BLUE)
    center_text('Hello, Yangyang', WHITE, BLUE, 2)
    print('DEMO SHOWN')
