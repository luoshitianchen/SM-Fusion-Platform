# SM Fusion Platform Desktop

Windows 桌面端使用原生 Tkinter 企业工作台读取融合门户服务目录，不复制 ERP 或知识库认证逻辑。新增项目后会自动显示，不需要重新构建客户端。先启动融合平台：

```powershell
docker compose up -d
```

再构建并启动桌面端：

```powershell
cd desktop
.\build.ps1
.\dist\SM-Fusion-Platform.exe
```

默认访问 `http://127.0.0.1:8200`。可通过 `SM_FUSION_PORTAL_URL` 指向企业内网网关地址。客户端在门户不可用时仅打开浏览器提示，不执行任意 shell 命令。

服务器模式可将 `desktop-config.example.json` 复制为与 EXE 同目录的 `desktop-config.json`，把 `portal_url` 改为企业 HTTPS 地址。同一安装包可用于本机和服务器模式，不需要重新编译。
