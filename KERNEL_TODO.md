# OnePlus 8 (instantnoodle) 主线内核工作 — 待办

> 目标树：**Xo666 6.16.7**，fork = `SQL0106/mainline-instantnoodle` branch `6.16.7`
> 源 commit：`408762bfe17332622560658f394f9cdbb1c9902e`（= 手机运行内核 6.16.7 #9, xo@debianlocalhost, 2026-01-09）
> 本文件 = 交接文档，给后续接手编内核的会话。详细调研见 opencode 压缩块 b20/b21/b22。

## 0. 当前状态（2026-10-02）

- GHA run **37014952443**（`.github/workflows/build-bootimg.yml`, workflow_dispatch）第一次 vanilla 构建已触发，启动 2026-10-02T13:43:59Z。
  - 查看：`gh run view 37014952443`（**不要挂长阻塞轮询**，用户会 abort；按需单次查）。
  - 成功后：`gh run download 37014952443 -n boot-img -D ~/kernel-build/out/`
  - 产物：`boot.img`（自编译 Image.gz + 自编译 dtb）、`boot-refdtb.img`（自编译 Image.gz + 参考 dtb，隔离 dtb 问题）、`built.dtb`、`config-drift.diff`。
- 打包器 `bootpack/pack_bootimg.py` 已做**字节级往返验证**（ROUNDTRIP_IDENTICAL，--pad-to 53477376）。参数 = 参考 `~/Flash/6.16.7_boot.img` 的精确值：header v0、page 4096、kernel 0x8000、ramdisk 0x01000000、second 0x00f00000、tags 0x100、cmdline `root=/dev/sda24 rw console=tty0 loglevel=3`（其余 androidboot.* 由 bootloader 追加）、id 字段留零、无 AVB footer。
- 参考镜像目录：`/home/SQL916/Flash/`（6.16.7_boot.img 53477376B、dtbo.img、rootfs-trixie.img 等）。
- 本地工作区 `~/kernel-build/`：parse_boot.py、bootpack/（pack_bootimg.py + config-6.16.7 + ramdisk_from_boot.img + dtb_appended.dtb + README）、repo/（sparse cone: .github bootpack + 根文件）、out/（产物落点）。
- **已做零构建项**（可直接用）：
  1. WireGuard 内核数据路径：`/etc/modules-load.d/wireguard.conf` 写入 `wireguard`，tailscaled 已重启确认走内核态（无 wireguard-go 进程）。
  2. Jellyfin：`/etc/jellyfin/encoding.xml`（备份 encoding.xml.bak-wg）`HardwareAccelerationType=v4l2m2m`（**硬解码实测可用**，Venus video14/15 在位）+ `EnableHardwareEncoding=false`（**硬编码段错误**，两版 ffmpeg rc=139，用户态问题，待查）。

## 1. 验证流水线（用户已确认的顺序）

1. **Vanilla 构建验证**：GHA 产出 boot.img → PC 上 `fastboot boot boot.img`（RAM 启动，**不写分区**，失败无限重试，断电回退原系统）。
   - 需 USB 连手机进 bootloader：`reboot bootloader`（Debian 里 systemd RESTART2，未实测）或关机 + 音量下 + 电源。
   - fedora 未装 android-tools（fastboot 小包装上即可；之前本地 dnf 被用户中止，因为当时不该本地编译，装 fastboot 本身没冲突）。
   - 判读：boot.img 不启 + boot-refdtb.img 启 ⇒ 自编译 dtb 问题；都不启 ⇒ kernel/打包问题。
   - bootloader 可能拒签 `fastboot boot` → 退路 = `fastboot flash boot`（**先 dd 备份 boot_a/boot_b**，分区 /dev/sde11、/dev/sde35，各 96MB；dtbo_a = sde17）。
2. **调试日志版**（验证期开，正式版关）：
   - cmdline `loglevel=7`、去掉 `printk.disable_uart=1`（改 pack 参数）。
   - **ramoops**：PSTORE_RAM/CONSOLE 已 =y，但 DT 无 reserved-memory ⇒ /sys/fs/pstore 空。在 dts 加 ramoops 节点才能失败后看日志。
   - 可选：CONFIG_NETCONSOLE（现 is not set）流式 dmesg 到 fedora；DETECT_HUNG_TASK、SOFTLOCKUP_DETECTOR、WQ_WATCHDOG。
3. **加特性/充电主线**（见 §2、§3）→ 再构建 → fastboot boot 验证。
4. **正式版**：关调试项 → 最终 `fastboot boot` 确认 → `fastboot flash boot` 固化（先备份）。

构建机结论：**GitHub Actions 为主**（用户指定，4vCPU/16G，估 20–25min）；200GE 本地仅当需要快迭代时备选；**绝不在手机上编**。

## 2. 配置新增清单（下次构建的 .config 变更）

在 `bootpack/config-6.16.7`（= /boot/config-6.16.7, 8634 行, 由 op8_defconfig 派生）基础上：

**常驻候选（与用途）**
- `TCP_CONG_ADVANCED=y` + `TCP_CONG_BBR=y` + `NET_SCH_FQ=y` — 吞吐（当前仅 cubic）
- `TLS=y` — 内核 TLS
- `MPTCP=y` — 多路径
- `LRU_GEN=y` + `LRU_GEN_ENABLED=y` — MGLRU
- `USERFAULTFD=y` — CRIU 快照
- `THERMAL_NETLINK=y` — 用户态温控守护（当前无 thermal daemon）
- `EROFS_FS=y` — 容器镜像（当前 is not set；steamed-noodle 用 erofs-fuse 兜底）
- `ANDROID_BINDERFS=y` — Waydroid（BINDER_IPC 已 =y，binderfs 缺）
- `IKHEADERS=y` — bpftrace/kernel headers
- `KPROBES=y` + `DEBUG_INFO_BTF=y`（需装 dwarves/pahole；要关 DEBUG_INFO_REDUCED）— 动态追踪
- `SECURITY_APPARMOR` 或 `SECURITY_LANDLOCK` — 可选（当前 LSM 串里没有）

**验证版专属**：`DETECT_HUNG_TASK=y`、`SOFTLOCKUP_DETECTOR=y`、`WQ_WATCHDOG=y`、`NETCONSOLE=y`（+ramoops dts）
**排除**：`VIRTUALIZATION`（ktap 显示 `All CPU(s) started at EL1` ⇒ 无 EL2，KVM 不可能）
**充电主线必开**：`CHARGER_QCOM_SMB2=y`（当前 is not set；Makefile 映射到 qcom_pmi8998_charger.o）

改法：直接改 bootpack/config-6.16.7 后 commit（workflow 用它 + olddefconfig，漂移记 config-drift.diff），或 workflow 内 `scripts/config` 注入。

## 3. 充电主线（70%/30% 电池保护 — 核心特性）

背景：内核无 charger 驱动（SMBB/SMB2 均 not set），power_supply 只有 bq27411-0 电量计 + tcpm USB；无任何可写充电控制属性。用户需求 = **充到 70% 停、掉到 30% 续**。

三件套（全部调研完毕，缺一不可）：

1. **DT 补丁**：`GabrielCRadu/steamed-noodle` 的 `pmaports/linux-oneplus-instantnoodle/0001-port-charger-fg-from-wuerfeldev.patch`
   - 加 `charger@1000`（compatible `qcom,pm8150b-charger`，4 irq：bat-ov/usbin-plugin/usbin-icl-change/wdog-bark，io-channels usb_in_i_uv + usb_in_v_div_16 + chg_sbux + vph_pwr + chg_temp）+ `fuel-gauge@4000`（`qcom,pm8150b-fg`）+ ADC channel@7/8（pm8150b_adc）+ @83/@99（instantnoodle dts）+ status okay + monitored-battery/power-supplies。
   - 该补丁只在 Xo666 树上编译验证过、**从未上真机** —— 因为树里没有驱动（见 2）。GPU/zap-shader 不受影响。
2. **驱动绑定（一行）**：`drivers/power/supply/qcom_pmi8998_charger.c`（Xo666 树中该文件 ≈ 上游 v6.16，仅 3 行 wakeup-irq 差异）of_device_id（~line 1034）只有 `qcom,pmi8998-charger`/`qcom,pm660-charger`，加：
   ```c
   { .compatible = "qcom,pm8150b-charger", .data = "pm8150b" },
   ```
   驱动 probe 依赖：SPMI 父 regmap、reg base 0x1000、IIO `usb_in_v_div_16`+`usb_in_i_uv`（`qcom_spmi_adc5` 模块已在手机加载，.ko 存在）、上述 4 个具名 IRQ、DT monitored-battery。`qcom_spmi_adc5` 依赖已验证 ✅。
   社区先例（同策略已 4 树）：danascape/linux-billie、MCC45TR/nabu-linux-kernel、eng-brener/hanoip-mainline、GH4NG/meizu-m1882-mainline-linux（都在 qcom_smbx.c 加 of_device_id）。独立驱动变体：itzreesa/sm8250-mainline `drivers/power/supply/qcom_pm8150b_charger.c`（26774B，GPL，sm8250 同平台）。
3. **charge_behaviour 属性（~30 行新代码）**：驱动原生只暴露 CURRENT_MAX（→ USBIN_CURRENT_LIMIT_CFG 0x370, /50000, max 4.95A），**没有** charge_behaviour，上游核心也没实现阈值滞回。需实现 `POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR`（texts: auto / inhibit-charge / inhibit-charge-awake / force-discharge），打寄存器 `CHARGING_ENABLE_CMD 0x42` BIT(0)（备选：CHGR_CFG2 0x51 CHARGER_INHIBIT_BIT；USBIN_CMD_IL 0x340 USBIN_SUSPEND_BIT）。具体寄存器语义要对照 [WuerfelDev/linux-sm8250](https://gitlab.com/WuerfelDev/linux-sm8250)（branch `6.17.0-instantnoodle`，pmOS 树）的实现核对。
4. **用户态守护（70/30 滞回）**：systemd 单元读 `/sys/class/power_supply/bq27411-0/capacity`：≥70 写 `inhibit-charge`，≤30 写 `auto`。电量计换新电池后已正常（容量%、4.1V、充电电流真实）。
   - 兜底：若驱动始终不暴露开关 → 智能插座/HA 方案（用户未确认有无）。

**风险**：本机史上首次 "GPU 正常 + charger 驱动绑定" 组合（WuerfelDev 树 GPU 被禁、ObiKeahloa 缺 zap-shader —— 没有树同时做到）。回退 = fastboot boot 不固化 / boot 分区备份。

## 4. 其他待查

- **Jellyfin/ffmpeg v4l2m2m 硬编码 segfault**（rc=139，/usr/bin/ffmpeg 7.1.5 与 jellyfin-ffmpeg 均崩；解码正常）：用户态封装 bug，待排查；修好后把 `EnableHardwareEncoding` 改回 true。
- 手机侧日志器 crashtap/ktap 仍 enabled+active（诊断历史掉电用，勿删）。
- dtbo：自编译 dtb 与参考 dtb 可能不同（config-drift/built.dtb 供比对）；dtbo.img 分区未动。
- 参考 ramdisk：`bootpack/ramdisk_from_boot.img`（原样复用，不重编 initrd）。

## 5. 环境 / 红线

- 手机 root 远程：`printf '%s\\n' \"$SUDO_PASS\" | SSH_ASKPASS=~/.ssh/askpass.sh SSH_ASKPASS_REQUIRE=force ssh -o BatchMode=no server 'sudo -S -p \"\" bash -s'`（多命令用 stdin 喂脚本；远端 shell 无 SUDO_PASS）。
- **NEVER `pkill -f <pat>`** —— 会匹配调用方 SSH shell 的命令行把自己杀掉；用 `pkill -x <name>`。
- gh 已认证 SQL0106（fork 权限）；DDG MCP 出口 IP 不干净常失败 → 用 `gh api`/curl/gitlab API。
- 重要文件**不写 /tmp**（掉电丢文件，已实证 0-byte 事故）→ 一律 ~/kernel-build/ 或仓库内。
- git：本地身份 SQL916_Fedora，`gh auth setup-git` 已跑；fork 推送直推 branch 6.16.7。
- 手机 = OnePlus 8 (SM8250)，Debian 13 aarch64，boot 走 boot.img 分区不是 /boot 目录；`dpkg -i` 新内核**不会**改变启动项。
- 需要装 fastboot 时：`sudo dnf install android-tools`（仅工具，不涉及编译）。
