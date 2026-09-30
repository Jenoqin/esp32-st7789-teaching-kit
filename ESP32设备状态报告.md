# ESP32 + WLK1501SPI-8P 彩屏 设备详情报告

> 检测时间：2026-09-29
> 检测方式：串口读取 + MicroPython REPL 查询 + esptool 直读芯片
> 端口：COM3（115200）

---

## 一、结论速览

| 项目 | 状态 |
|---|---|
| USB 连接 | ✅ 正常（COM3，CP210x 驱动已装） |
| ESP32 芯片 | ✅ **ESP32-D0WD-V3**，revision v3.1 |
| 固件 | MicroPython v1.29.0（2026-08-24 构建） |
| Flash | ✅ 4MB，厂商 0x5E（Zbit），3.3V |
| 用户程序 `main.py` | ✅ 已执行完毕，打印 `HELLO SHOWN` |
| 显示屏 | ✅ 已点亮，显示 `Hello, Yangyang`（蓝底白字） |
| 屏型号 | WLK1501SPI-8P，驱动 IC **ST7789**，**240×240** |
| 待修问题 | ⚠️ 代码按 240×320 写入，与实际 240×240 不符，画面偏移（见第九节第 6 条） |
| 串口日志 | ⚠️ 仅在启动时输出一次，之后静默（正常） |

---

## 二、ESP32 芯片（esptool 直读，权威）

```
Chip type:          ESP32-D0WD-V3 (revision v3.1)
Features:           Wi-Fi, BT, Dual Core + LP Core, 240MHz,
                    Vref calibration in eFuse, Coding Scheme None
Crystal frequency:  40MHz
MAC:                8c:94:df:xx:xx:xx
```

| 项 | 值 |
|---|---|
| 芯片型号 | **ESP32-D0WD-V3** |
| 芯片修订 | v3.1（较新的 ESP32 修订版，非早期 ECO0/1） |
| 内核 | Xtensa LX6 **双核** + LP 协处理器 |
| 最高主频 | 240MHz（当前 MicroPython 跑在 **160MHz**） |
| 无线 | Wi-Fi + 蓝牙（BT/BLE） |
| 晶体 | 40 MHz |
| Vref 校准 | 已烧录在 eFuse 中 |
| Coding Scheme | None（非 None 的编码方案会损失可用 Flash） |

**ROM 信息**：`ets Jul 29 2019 12:21:46`，`boot:0x13 (SPI_FAST_FLASH_BOOT)` —— 正常从 SPI Flash 启动，未卡在下载模式。

---

## 三、Flash 芯片

```
Manufacturer: 5e
Device: 4016
Detected flash size: 4MB
Flash voltage set by a strapping pin: 3.3V
```

| 项 | 值 |
|---|---|
| 厂商 ID | `0x5E` → **Zbit Semiconductor**（国产 SPI Flash 常见厂商） |
| 器件 ID | `0x4016`（类型 0x40，容量码 0x16 = 4MB） |
| 容量 | **4 MB** |
| 电压 | 3.3V（由 strapping 引脚决定） |
| PSRAM | **无**（`esp.psram_size()` = 0，仅内部 SRAM） |

---

## 四、网络身份

| 接口 | MAC |
|---|---|
| STA（站模式） | `8C:94:DF:xx:xx:xx` |
| AP（热点模式） | `8C:94:DF:xx:xx:xx(+1)` |

（两地址连续，AP = STA + 1，符合 ESP32 默认行为）

---

## 五、固件与资源

| 项 | 值 |
|---|---|
| 固件 | MicroPython **v1.29.0**，构建于 2026-08-24 |
| 平台标识 | `Generic ESP32 module with ESP32` |
| CPU 实际频率 | 160 MHz |
| 文件系统 | 总 2 MB，剩余约 **2008 KB** |
| RAM | 启动后空闲约 157 KB；REPL 会话中约 113 KB |

> 注：这版构建**裁剪掉了** `esp.flash_id()`、`esp32.hall_sensor()`、`esp32.mcu_temperature()`，
> REPL 里调用会报 `AttributeError`。想拿这些值需换固件或用 esptool。

---

## 六、显示屏（已更正）

这块屏 **不是 I2C OLED**，是 **SPI 接口 TFT 彩屏**：

| 项 | 值 |
|---|---|
| 模块型号 | **WLK1501SPI-8P**（背板丝印确认） |
| 驱动 IC | **ST7789**（Sitronix 矽创）—— 背板丝印 `IC:ST7789` 直接确认 |
| 分辨率 | **240 × 240**（背板丝印 `Pixel240*240`）⚠️ 与代码里的 320 不符，见下 |
| 色彩格式 | RGB565（每像素 16 bit） |
| 接口 | 4 线 SPI（SCL / SDA / DC / CS）+ RES + BL |
| SPI 速率 | 20 MHz（`SPI(1)`，CPOL=0, CPHA=0） |
| 是否可读 | ❌ **只写**——8 针版本未引出 SDO/MISO |
| 厂商 | 背板丝印 `WWW.WLKJLCD.COM` |
| PCB | UL 认证 `94V-0` / `E478892`，嘉立创打样（`JLC-3`） |
| 触摸 | 背板 `P3` 标注 `CTP_IC`，**预留电容触摸 IC 位置但未焊接**，本模块无触摸 |

> ⚠️ **重要：分辨率与代码不一致**
> 实物是 **240×240**，而 `main.py` 里写的是 `WIDTH, HEIGHT = 240, 320`。
> ST7789 的显存是 240×320，240×240 面板只是其中一块窗口，通常需要设置行偏移
> （常见为 rowstart=80，即 RASET 从 80 到 319）。
> 当前代码按 0~319 写入，画面会**整体上移约 80 行**，文字不在正中央。
> 修正方法见第九节第 6 条。

### 引脚接线

顶部 8 针排针，丝印顺序（以实物为准）：

`GND → CS → DC → RES → SDA → SCL → VCC → BLK`

| 屏幕丝印 | 作用 | ESP32 GPIO | 代码变量 |
|---|---|---|---|
| GND | 地 | GND | — |
| CS | 片选（低有效） | 5 | `CS` |
| DC | 命令/数据选择 | 2 | `DC` |
| RES | 硬件复位（低有效） | 4 | `RST` |
| SDA | SPI 数据（MOSI） | 23 | `MOSI` |
| SCL | SPI 时钟 | 18 | `SCK` |
| VCC | 电源 **3.3V**（勿接 5V） | 3V3 | — |
| BLK | 背光控制 | 19 | `BL` |
| （无此脚） | MISO | 34 — 代码里写了但**无实际连线**，读回恒为 0xFF | `miso` |

> 板上另有：`Q1`（三极管，驱动背光）、`R1~R4`（限流/上拉）、`U1`、`U3`、`C2`，
> 以及 `P2`/`P3` 焊盘，其中 `P3` 对应 `CTP_IC`（触摸预留位）。

> **驱动 IC 确认依据**：背板丝印直接标注 `IC:ST7789`，实物证据确凿。
> 补充：这块屏无 MISO，无法通过 `0x04` 读 ID 自报家门（实测返回 `ff ff ff ff`，
> MISO 悬空上拉），"读寄存器"这条路走不通；且其初始化序列
> （`0xB2/0xB7/0xBB/0xC0~0xC6/0xD0/0xE0/0xE1` + `INVON`）与 ILI9341 高度相似，
> 仅凭命令序列推断极易误判 —— 这正是丝印的价值所在。

---

## 七、板载文件

```
boot.py            breath2s.py      led-pin2.py
main.py            sweep.py         sweep_log.txt
web-led-ctl.py     wifi-con.py
```

`boot.py` 是 MicroPython 默认模板，**全部注释掉，无实际初始化动作**。
上电后真正执行的是 `main.py`（屏幕初始化 + 显示 `Hello, Yangyang` + 打印 `HELLO SHOWN`）。

---

## 八、还无法从软件确定的信息

| 想知道的 | 能否软件获取 | 怎么确认 |
|---|---|---|
| **开发板型号**（DevKitC / NodeMCU-32S / LOLIN32 …） | ❌ 否 | 需看板子丝印，通常在 USB 口附近或板背；MicroPython 只报 `Generic ESP32 module` |
| 屏幕物理尺寸（1.3" / 1.54"） | ❌ 否 | 丝印未标尺寸；240×240 常见于 1.3" / 1.54" 面板，量对角线即可确认 |
| 屏幕是否带触摸 | ✅ 已知 | 背板 `P3` 预留 `CTP_IC` 位置但**未焊接**，本模块无触摸功能 |
| 芯片温度 | ❌（本固件裁剪） | 换官方固件后可用 `esp32.mcu_temperature()` |

**已知线索**：USB 桥接用的是 **CP210x**（不是 CH340），常见于乐鑫官方 DevKitC、NodeMCU-32S、WEMOS LOLIN32 等板子。

---

## 九、使用注意事项

1. **严禁 `I2C.scan()` 盲扫引脚。** 在 GPIO18/19 上初始化 I2C 会抢占 SPI 的 SCL 与背光 BL，
   屏幕当场熄灭并刷大量 `I2C hardware timeout`。恢复方法：复位一次（按板上 RST 键），
   `main.py` 会重新配置引脚并恢复显示。
2. **打开串口会触发一次复位**（DTR/RTS 电平变化），属正常现象，屏幕会闪一下重绘。
3. **串口独占**：Thonny、esptool、pyserial 同一时刻只能有一个占用 COM3，
   报"拒绝访问"时先关掉 Thonny（包括其后台进程）。
4. **SPI 速率别超 20MHz**：你这版固件在 40MHz 下会触发 `Guru Meditation Error`
   并无限重启；若发生在 `main.py` 里会造成上电死循环，需抢在启动时 Ctrl+C 中断并删除 `main.py`。
5. esptool 会短暂进入下载模式再自动复位，屏幕会闪一次后自动恢复（已实测确认）。
6. **分辨率不匹配（待修）**：实物屏为 **240×240**，`main.py` 写的是 240×320。
   ST7789 显存是 240×320，240×240 面板只用到其中一块窗口，通常需要行偏移
   （常见 rowstart=80）。当前代码按 0~319 写入，画面会**整体上移约 80 行**，文字不居中。
   两种改法：
   - **简单**：把 `HEIGHT` 改成 240，让内容填满整个面板（居中逻辑会重新计算）。
   - **正规**：保留 320 显存，在 `init()` 里把窗口对齐到面板并同步 `show()` 的行范围，
     例如 RASET 设为 80~319：`cmd(0x2B, b'\x00\x50\x01\x3f')`。
   建议先用一个已知位置的方框实测落点，再决定偏移量。

---

## 十、常用命令速查

```bash
# 芯片与 Flash 权威信息（会复位一次，之后自动恢复）
python -m esptool --port COM3 chip-id
python -m esptool --port COM3 flash-id
python -m esptool --port COM3 read_mac

# 本项目脚本
python esp32_check.py COM3          # 枚举串口 + 抓启动日志
python esp32_repl_probe.py COM3     # REPL 只读查询系统/文件/屏幕引脚
python esp32_detail_probe.py COM3   # 深度探测芯片/Flash/MAC/屏幕寄存器
```

Python 环境（已装 pyserial + esptool）：
`C:/Users/jenoq/.workbuddy/binaries/python/envs/default/Scripts/python.exe`

---

## 十一、商家商品文案核对

商家提供的是 **ESP32-WROOM-32 模组的通用规格模板**，描述的是"芯片能做什么"，
不是"这块开发板装上 MicroPython 后当前能做什么"。逐条核对如下。

| 文案声明 | 实测 / 事实 | 判定 |
|---|---|---|
| 核心是 ESP32 **WOWDQ6** 芯片 | 实测 **ESP32-D0WD-V3 (revision v3.1)** | ⚠️ 文案拼写有误，应为 `D0WDQ6`；且实物是更新的 V3 版本 |
| 两个 Xtensa 32-bit LX6 核可被单独控制 | esptool：`Dual Core + LP Core` | ✅ 属实 |
| 运算能力高达 600 MIPS | 240MHz × 2 核的理论峰值 | ✅ 理论值（宣传口径，非实测） |
| 时钟频率 80–240 MHz | 支持；当前 MicroPython 运行在 160MHz | ✅ 属实 |
| 448KB ROM | 芯片内置 ROM（存放启动代码） | ✅ 属实（用户不可使用） |
| 520KB SRAM | 芯片物理容量；**用户实际可用约 157KB** | ⚠️ 数字属实，但远小于"可用内存" |
| 16KB RTC SRAM | 供 LP 协处理器/深睡使用 | ✅ 属实 |
| 模组集成 4MB **QSPI** FLASH | 容量 4MB ✅；但当前运行在 **DIO** 模式（`mode:DIO, clock div:2`） | ⚠️ 容量对，接口模式是 DIO 不是 QIO |
| 可切断 CPU 电源，用低功耗协处理器监测外设 | ULP 协处理器 | ✅ 芯片有（本固件未编译该支持） |
| 电容式传感模块 | 触摸传感 | ⚠️ 芯片有，**本固件裁剪**（`esp32.TouchPad` 不存在） |
| 霍尔传感器 | 芯片有 | ⚠️ 芯片有，**本固件裁剪**（`esp32.hall_sensor()` 不存在） |
| 低噪声传感放大器 | SENSOR_VP / SENSOR_VN 通道 | ✅ 芯片有 |
| SD 卡接口 | SDMMC 外设 | ✅ 芯片有，需外接卡座才能用 |
| 以太网接口 | 内置 EMAC | ⚠️ 需外接 PHY 芯片才能用 |
| 高速 SDIO / SPI / UART / I2S / I2C | 硬件外设 | ✅ 属实 |

### 文案没写、但实测发现的

- **Flash 厂商是 Zbit（`0x5E`）**，国产第三方颗粒，非 Espressif 原装。日常玩无碍，
  批量产品或长期可靠性需要考虑这一点（不同批次颗粒可能不同）。
- **无 PSRAM**（`esp.psram_size()` = 0）。
- 串口桥接用 CP210x（不是更廉价的 CH340），这算是加分项。

### 一句话结论

文案参数虚标不多，但属于**芯片级"能力清单"**。真正落地时会打折：
520KB SRAM 实际可用约 157KB；霍尔、触摸等外设在 MicroPython 里被裁掉；
以太网、SD 卡要外接器件；QSPI Flash 当前跑的是 DIO 模式。

---

## 十二、显示屏接线速查（跨任务复用）

本章供后续任何任务直接取用：照此接线与配置即可点亮屏幕，无需重新探测。
所有数据均来自实测（esptool 读芯片 + 读板上 `main.py` + 屏幕背板丝印核对）。

### （一）接线总览

屏幕排针共 8 针，丝印顺序为 `GND → CS → DC → RES → SDA → SCL → VCC → BLK`。

| 屏幕丝印 | 实际含义 | ESP32 引脚 | 代码常量 |
|---|---|---|---|
| GND | 地 | GND | — |
| CS | 片选 | GPIO 5 | `CS` |
| DC | 命令 / 数据选择 | GPIO 2 | `DC` |
| RES | 复位 | GPIO 4 | `RST` |
| SDA | **MOSI**（SPI 数据输出） | GPIO 23 | `MOSI` |
| SCL | **SCK**（SPI 时钟） | GPIO 18 | `SCK` |
| VCC | 电源 | 3.3V | — |
| BLK | 背光控制 | GPIO 19 | `BL` |

> **最易误判的一点**：丝印写的是 `SDA / SCL`，外观像 I2C，**实际是 SPI**。
> 其中 `SDA` = MOSI（主机→屏幕），`SCL` = SCK（时钟）。按 I2C 接线或执行
> `I2C.scan()` 会直接抢占 GPIO18 与 GPIO19，导致屏幕熄灭。

> **VCC 电压**：当前按 3.3V 接法工作正常。同型号模块部分批次板载稳压可接 5V，
> 请以自身模块标注为准，不要仅凭型号判断。

尚无回读通道：8 针版本未引出 MISO / SDO，屏幕为**单向只写**。

### （二）关键工作参数

| 参数 | 取值 | 越界后果 |
|---|---|---|
| SPI 总线 | `SPI(1)`，CPOL=0，CPHA=0 | — |
| SPI 速率 | **≤ 20 MHz** | 40 MHz 会触发 `Guru Meditation Error` 并无限重启；若写进 `main.py` 将变成上电死循环 |
| 分辨率 | **240 × 240** | 按 320 行写会多刷 80 行，且画面不居中 |
| 行列地址窗口 | 0–239 × 0–239 | 同上 |
| 行偏移 rowstart | **0**（实测确认） | 与常见 240×240 模块的 80 不同，勿照抄网络示例 |
| MADCTL | `0x00` | 与 INVON 配合后颜色正确 |
| 反色 | 必须开 `0x21`（INVON） | 不开则颜色反相 |
| 色深 | RGB565（COLMOD `0x55`） | — |
| 回读 | **不支持** | `spi.read()` 恒为 `0xFF`，读 ID 永远拿不到 |

### （三）初始化命令序列

| 命令 | 参数 | 作用 |
|---|---|---|
| 硬件复位 | RES 拉低 20 ms 后拉高，等待 150 ms | 复位驱动 IC |
| `0x01` | — | SWRESET 软件复位，等待 150 ms |
| `0x11` | — | SLPOUT 退出睡眠，等待 120 ms |
| `0x3A` | `0x55` | COLMOD 设为 RGB565 |
| `0x36` | `0x00` | MADCTL 扫描方向 |
| `0xB2` | `0C 0C 00 33 33` | 帧率与 porch 控制 |
| `0xB7` | `72` | 栅极驱动 |
| `0xBB` | `3D` | VCOM 设置 |
| `0xC0` | `2C` | LCM 控制 |
| `0xC2` | `01 FF` | VDV / VRH 使能 |
| `0xC3` | `19` | VRH 设置 |
| `0xC4` | `20` | VDV 设置 |
| `0xC6` | `0F` | 帧率控制 |
| `0xD0` | `A4 A1` | 电源控制 |
| `0xE0` | `D0 04 0D 11 13 2B 3F 54 4C 18 0D 0B 1F 23` | 正伽马 |
| `0xE1` | `D0 04 0C 11 13 2C 3F 44 51 2F 1F 1F 20 23` | 负伽马 |
| `0x21` | — | INVON 反色（IPS 屏必须） |
| `0x29` | — | DISPON 开显示 |

> 该序列与 ILI9341 高度相似，曾被误判为 ILI9341；驱动 IC 已由背板丝印
> `IC:ST7789` 确认。

### （四）启动确认流程

1. 按上表接好 8 根线，上电。
2. 板子自动执行 `main.py`：屏幕显示蓝底白字 `Hello, Yangyang`，串口末尾打印
   `HELLO SHOWN`。**看到这行即表示接线与 SPI 均正常**（全程约 4.8 秒）。
3. 串口参数：**COM3，115200**。Thonny 中选解释器 MicroPython (ESP32)、端口 COM3。
4. 串口为独占资源，Thonny、esptool、pyserial 同时只能有一个占用 COM3。
5. 打开串口会触发一次复位并重跑 `main.py`，因此**须先等待约 3 秒**再发命令，
   否则命令会被丢弃。

### （五）禁止事项

| 不要做 | 原因 |
|---|---|
| 用 `I2C.scan()` 盲扫引脚 | 会抢占 GPIO18（SCK）与 GPIO19（背光），屏幕当场熄灭并输出 `I2C hardware timeout`；误伤后按 RST 复位即可恢复 |
| SPI 速率超过 20 MHz | 崩溃重启；若写进 `main.py` 会造成上电死循环，需在启动时 Ctrl+C 中断并删除 `main.py` |
| 将 GPIO2 用作 LED 或其它用途 | GPIO2 是屏幕 DC。板载 LED 若物理焊在 GPIO2 上与 DC 并联，则无法用软件分开，会随屏幕数据闪动 |
| 指望从屏幕读数据 | 无 MISO。曾盲扫 4080 种引脚组合，零命中 |
| 调用 `esp.flash_id()` / `esp32.hall_sensor()` / `esp32.mcu_temperature()` / `TouchPad` | 本版固件已裁剪，调用直接报 AttributeError；芯片信息改用 esptool 查询 |

### （六）常见故障排查

| 现象 | 原因与处理 |
|---|---|
| 屏幕全黑 | 检查 BLK（GPIO19）是否置高；检查 VCC 与 GND |
| 花屏、乱点 | 多半是其它脚本重配了 GPIO2 / 5 / 18 / 19 / 23，按 RST 复位 |
| 颜色反相 | 缺少 `0x21`（INVON） |
| 颜色偏色 | 字节序问题，对调颜色高低字节，或在 MADCTL 加 `0x08`（BGR） |
| 文字偏上或偏下 | `HEIGHT` 与面板不符。本屏 rowstart=0，应使用 240 |
| 上电无限重启 | SPI 速率过高。Ctrl+C 中断后删除 `main.py`，降回 20 MHz |
| 串口无输出 | 正常，仅在启动末尾打印一次；持续输出需在代码中加 `print()` |
| 命令无响应 | 打开串口后未等启动完成（应等 3 秒），或 REPL 被 `main.py` 长时间占用 |
| 读屏幕 ID 全为 `FF` | 正常，无 MISO 回读通道 |
| COM3 打不开 | 多半被 Thonny 占用，先关闭 |
