# bootpack — 参考 boot.img（/home/SQL916/Flash/6.16.7_boot.img）解包产物

参考镜像 `6.16.7_boot.img`（53,477,376 B = 51 MiB，尾部补零）已验证 header v0 打包参数：

| 字段 | 值 |
|---|---|
| header_version | 0（dt_size=0） |
| page_size | 4096 |
| kernel_addr | 0x00008000 |
| ramdisk_addr | 0x01000000 |
| second_addr | 0x00f00000 |
| tags_addr | 0x00000100 |
| cmdline | `root=/dev/sda24 rw console=tty0 loglevel=3`（bootloader 另加 androidboot.*） |
| id | 全零（原打包器不算 sha1） |
| AVB | 无签名/无 footer |
| 内嵌 dtb | 无（dtb 以 gzip 流后附带 FDT 形式存在） |

kernel 布局：`Image.gz`（14,883,486 B，gzip）+ 附带 dtb（134,782 B，magic d00dfeed）。
ramdisk：gzip cpio（20,853,843 B）。

- `pack_bootimg.py`：header v0 打包器，**与参考镜像字节级往返一致**（ROUNDTRIP_IDENTICAL）。
- `config-6.16.7`：手机 /boot/config-6.16.7（md5 ef2b8e7d6f91d9b3abb9fa6d7a54d3e7，8634 行）。
- `ramdisk_from_boot.img`：参考镜像内 ramdisk 原样复用。
- `dtb_appended.dtb`：参考镜像附带 dtb（md5 c4bbb99314570472c83f254916e73365），用于 boot-refdtb.img 变体。

workflow 产物：
- `boot.img` = 自编译 Image.gz + 自编译 dtb（全 vanilla）
- `boot-refdtb.img` = 自编译 Image.gz + 参考 dtb（若 boot.img 不启动、boot-refdtb 启动 ⇒ dtb 构建问题；都不启动 ⇒ kernel 构建/打包问题）
