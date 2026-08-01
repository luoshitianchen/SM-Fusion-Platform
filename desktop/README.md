# SM Fusion Platform Desktop

Windows 桌面端使用原生 Tkinter 企业工作台读取融合门户服务目录，不复制 ERP 或知识库认证逻辑。新增项目后会自动显示，不需要重新构建客户端。先启动融合平台：

```powershell
docker compose up -d
```

再启动桌面端：

```powershell
cd desktop
.\start.cmd
```

默认访问 `http://127.0.0.1:8200`。可通过 `SM_FUSION_PORTAL_URL` 指向企业内网网关地址。客户端在门户不可用时仅打开浏览器提示，不执行任意 shell 命令。

服务器模式可将 `desktop-config.example.json` 复制为同目录的 `desktop-config.json`，把 `portal_url` 改为企业 HTTPS 地址。同一桌面包可用于本机和服务器模式。

正式发布包使用 PyInstaller 目录模式，避免单文件自解压结构，并同时保留可审查源码。发布前对完整目录执行 Microsoft Defender 扫描。企业正式分发仍应使用组织代码签名证书签名 EXE/MSIX。
