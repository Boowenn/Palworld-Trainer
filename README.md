# Palworld 修改器 · 傻瓜版

一个开箱即用的 Palworld 修改器：下载 `PalworldTrainer.exe`，双击打开，进游戏，然后点按钮就行。

所有功能都是标准 Windows GUI，中文界面、分类清晰，不用记任何命令。

**v1.2 起「外挂」Tab 完全不需要任何 mod** — 修改器直接连接运行中的游戏进程，在内存里冻结 HP / 体力 / 移速 / 跳跃。

**v1.3 新增：**
- 外挂 Tab 的「自定义字段」—— 点一下模板（负重 / 饥饿 / 氧气 / 心情 / 武器冷却 / 弹药 / 耐久 / 当前经验 / …）就能冻结**任何**游戏里看得到的数字，走同一套扫描→缩小→锁定→冻结流程，不用写一行代码。
- 一键开挂预设：🛡 无敌 / ⚡ 无限体力 / 🏃 超级移速 / 🦘 超级跳跃 / 👼 神之模式 / 🛑 全部关闭。
- 新「命令」Tab：收录了社区文档里已知的 CCC v2+ 命令（godmode / infstam / infammo / nodur / noclip / unlockmap / unlockrecipes / healfull / fillstatus / homepoint / 雕像 / 手记 …），配上自由命令输入框 + 历史列表——任何 `@!` 命令都能直发。

---

## 能做什么

![Tabs](https://img.shields.io/badge/Tabs-9-blue) &nbsp; ![Items](https://img.shields.io/badge/物品-1900%2B-green) &nbsp; ![Pals](https://img.shields.io/badge/帕鲁-600%2B-orange) &nbsp; ![Tech](https://img.shields.io/badge/科技-500%2B-purple)

| Tab | 功能 |
|-----|------|
| **主页** | 游戏状态面板、启动游戏、连接进程（外挂）、打开游戏目录 |
| **玩家** | 切换飞行、脱困、打印坐标、解锁所有传送点、一键解锁全部科技、自定义经验、坐标传送 |
| **物品** | 7 种快捷礼包（新手 / 高级材料 / 顶级装备 / 弹药 / 食物 / 捕获 / 科技），1900+ 物品搜索 + 双击即给 |
| **帕鲁** | 600+ 帕鲁搜索 + 双击即生成 |
| **科技** | 一键解锁全部科技、一键解锁全部传送点、500+ 单项科技搜索 |
| **世界** | 时间滑块 + 清晨 / 正午 / 黄昏 / 午夜一键切换 |
| **外挂** | 直接内存外挂（**无需任何 mod**）— 首次搜索 → 缩小范围 → 锁定地址 → 冻结。HP / 体力 / 移动速度 / 跳跃初速度 四个固定槽位 + **无限自定义字段**（负重/饥饿/耐久/弹药/…）+ 一键开挂预设 |
| **命令** | 13 个实验性 `@!` 命令按钮 + 自由命令输入框 + 最近 20 条历史 |
| **设置** | 游戏目录浏览、环境扫描报告 |

> **注**：前 6 个 Tab 的快捷命令和「命令」Tab 都走游戏内聊天 `@!` 命令，需要 [Client Cheat Commands](https://www.nexusmods.com/palworld) 这个 mod。**外挂 Tab 是独立的直连内存路径，哪怕一个 mod 都不装也能用。**

---

## 快速开始

1. **下载修改器**：
   去 [Releases](https://github.com/Boowenn/Palworld-Trainer/releases/latest) 下载 `PalworldTrainer-v1.2.0-win64.exe`。

2. **双击运行**。程序会自动定位 Palworld 安装目录，加载 1900+ 物品 / 600+ 帕鲁 / 500+ 科技目录。

3. **打开游戏，进到世界里**（单人模式或你自己开的房间）。

4. **外挂 Tab（直连内存，无 mod 依赖）**：
   - 点「🎮 连接游戏」，程序会自动找到 Palworld 进程并连上
   - 在 HP 行填入你的**当前生命值**，点「首次搜索」（约 40 秒）
   - 回游戏里受点伤，再把新的 HP 填回来点「缩小范围」（秒级）
   - 候选数缩到 1 之后点「锁定」
   - 在「冻结目标」里填你想要的 HP（默认 9999），勾「冻结」
   - 后台每 50 ms 会把 HP 强制写回你设定的值
   - SP / 移动速度 / 跳跃初速度 流程完全相同

5. **聊天命令 Tab（可选，需要前置 mod）**：
   前提是装了 [Client Cheat Commands](https://www.nexusmods.com/palworld)。点按钮后程序会自动把 Palworld 窗口拉到前台，按回车打开聊天框，敲入对应的 `@!` 命令再回车发送。

---

## 工作原理

修改器内部有**两条独立路径**：

**路径一：聊天命令（前 6 个 Tab）**。通过 Win32 API 聚焦 Palworld 窗口，再用 `SendInput` 把 `@!giveme` / `@!spawn` / `@!unlockalltech` 等命令打到聊天框里，由第三方 mod [Client Cheat Commands](https://www.nexusmods.com/palworld) 执行。这条路径天然稳定、版本适配容易，但**需要装 mod**。

**路径二：直连进程内存（外挂 Tab，v1.2 新增）**。通过 `OpenProcess` / `ReadProcessMemory` / `WriteProcessMemory` 直接读写 `Palworld-Win64-Shipping.exe` 的进程内存。**没有 DLL 注入，没有文件改动，游戏完全 vanilla**，修改器一关游戏立刻恢复正常。

工作流是 Cheat Engine 风格的值扫描：

- 你填入当前真实数值（例如 HP=500），程序对进程的可写私有堆做一次 float32 精确扫描
- 你在游戏里把数值变一下（受伤 / 跑动 / 跳跃），填入新值，程序在上一次的候选集上二次筛选
- 候选缩到 1 个地址就锁定，后台线程每 50 ms 把目标值写回那个地址
- 四个槽位：HP、SP、`MaxWalkSpeed`、`JumpZVelocity`

本程序**不帮你**：
- 不用手动打命令
- 不用记物品 / 帕鲁 / 科技的内部 key
- 不用切到 `Mods/NativeMods/UE4SS/Mods/ClientCheatCommands/Scripts/enums/*.lua` 里找 id
- 按类别分好，方便批量操作

---

## 权限说明

- **单机 / 自己开房**：全部功能生效（你就是房主）。
- **加入别人的房间**：只有读取类命令（如坐标、显示帮助）保证生效。生成帕鲁、解锁科技这类修改共享世界状态的命令在非房主端通常会被主机拒绝——这是 Palworld 的 P2P 权威模型决定的，不是本程序的问题。

---

## 系统要求

- Windows 10 / 11 64-bit
- 已安装 Palworld
- **外挂 Tab**：不需要任何 mod，只要游戏在跑就能连接
- **聊天命令 Tabs**：需要 [Client Cheat Commands](https://www.nexusmods.com/palworld)（配套需要 UE4SS Experimental (Palworld)），且游戏以**窗口**或**无边框窗口**方式运行（独占全屏下按键注入不稳定），聊天打开键保持默认的 Enter

---

## 从源码运行

```powershell
git clone https://github.com/Boowenn/Palworld-Trainer.git
cd Palworld-Trainer
python -m palworld_trainer
```

## 从源码打包

```powershell
pip install pyinstaller
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1 -Clean
```

构建产物在 `dist\PalworldTrainer.exe`。

## 运行测试

```powershell
python -m unittest discover -s tests
```

---

## 目录结构

```
src/palworld_trainer/
    app.py            # tkinter 主界面
    game_control.py   # Win32 窗口 + SendInput 注入（聊天命令路径）
    commands.py       # @! 命令构建器 + 礼包定义
    catalog.py        # 物品/帕鲁/科技目录解析
    memory.py         # OpenProcess / RPM / WPM / AOB & 值扫描
    mem_engine.py     # 扫描-缩小-锁定-冻结 工作流 + 后台 50 ms ticker
    environment.py    # 游戏安装扫描
    config.py         # 设置持久化
    data/enums/       # 打包进 exe 的 ClientCheatCommands 目录快照
```

---

## 许可与致谢

- 游戏内作弊命令由 [KoZ 的 Client Cheat Commands](https://www.nexusmods.com/palworld) 提供，本程序仅做 GUI 包装。
- UE4SS 运行时由 [UE4SS](https://github.com/UE4SS-RE/RE-UE4SS) 团队提供。
- 物品 / 帕鲁 / 科技目录快照来自 ClientCheatCommands 的 `enums/*.lua`（自动从 Palworld Dataminer 生成），随本程序一同分发。

本程序仅供**单机或自建房间娱乐使用**。不要用它去骚扰别人的服务器或影响他人游戏体验。
