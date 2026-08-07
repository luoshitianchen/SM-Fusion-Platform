from __future__ import annotations

import json
import os
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import requests

DESKTOP_VERSION = "2.0.0"
LATEST_RELEASE_API = "https://api.github.com/repos/luoshitianchen/SM-Fusion-Platform/releases/latest"
RELEASES_URL = "https://github.com/luoshitianchen/SM-Fusion-Platform/releases/latest"


def desktop_config_path() -> str:
    base = os.path.dirname(sys.executable if getattr(sys, "frozen", False) else __file__)
    return os.path.join(base, "desktop-config.json")


def portal_url() -> str:
    if configured := os.getenv("SM_FUSION_PORTAL_URL"):
        return configured.rstrip("/")
    try:
        with open(desktop_config_path(), encoding="utf-8") as handle:
            value = str(json.load(handle)["portal_url"]).rstrip("/")
            if not value.startswith(("http://", "https://")) or "@" in value.split("://", 1)[-1].split("/", 1)[0]:
                raise ValueError("portal_url must be HTTP(S) without credentials")
            return value
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "http://127.0.0.1:8200"


class FusionDesktop(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.base_url = portal_url()
        self.title("SM Fusion Platform")
        self.geometry("1180x760")
        self.minsize(900, 620)
        self.configure(bg="#07111f")
        self.cards = ttk.Frame(self)
        self._configure_styles()
        self._build_layout()
        self.refresh()
        threading.Thread(target=self._check_update, daemon=True).start()

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Root.TFrame", background="#07111f")
        style.configure("Panel.TFrame", background="#0c1b2e")
        style.configure("Title.TLabel", background="#07111f", foreground="#e8f0ff", font=("Microsoft YaHei UI", 28, "bold"))
        style.configure("Body.TLabel", background="#07111f", foreground="#92a9c4", font=("Microsoft YaHei UI", 11))
        style.configure("CardTitle.TLabel", background="#0c1b2e", foreground="#e8f0ff", font=("Microsoft YaHei UI", 15, "bold"))
        style.configure("CardBody.TLabel", background="#0c1b2e", foreground="#92a9c4", font=("Microsoft YaHei UI", 10))
        style.configure("Healthy.TLabel", background="#0c1b2e", foreground="#4ed6a3", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Down.TLabel", background="#0c1b2e", foreground="#f0aa67", font=("Microsoft YaHei UI", 10, "bold"))
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(14, 9))

    def _build_layout(self) -> None:
        root = ttk.Frame(self, style="Root.TFrame", padding=28)
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root, style="Root.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=f"SM · ENTERPRISE AI FABRIC  v{DESKTOP_VERSION}", style="Body.TLabel").pack(side="left")
        self.state_label = ttk.Label(header, text="正在连接", style="Body.TLabel")
        self.state_label.pack(side="right")
        ttk.Label(root, text="多态融合企业智能平台", style="Title.TLabel").pack(anchor="w", pady=(38, 8))
        ttk.Label(root, text="统一访问融合门户、ERP、知识库以及后续注册的企业项目", style="Body.TLabel").pack(anchor="w")
        toolbar = ttk.Frame(root, style="Root.TFrame")
        toolbar.pack(fill="x", pady=(24, 14))
        ttk.Button(toolbar, text="刷新状态", style="Primary.TButton", command=self.refresh).pack(side="left")
        ttk.Button(toolbar, text="打开融合门户", command=lambda: webbrowser.open(self.base_url)).pack(side="left", padx=10)
        self.update_button = ttk.Button(toolbar, text="检查更新", command=lambda: webbrowser.open(RELEASES_URL))
        self.update_button.pack(side="left")
        ttk.Label(toolbar, text=f"服务地址：{self.base_url}", style="Body.TLabel").pack(side="right")
        self.summary = ttk.Label(root, text="服务状态加载中", style="Body.TLabel")
        self.summary.pack(anchor="w", pady=(4, 12))
        self.cards = ttk.Frame(root, style="Root.TFrame")
        self.cards.pack(fill="both", expand=True)

    def refresh(self) -> None:
        self.state_label.configure(text="正在刷新")
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self) -> None:
        try:
            response = requests.get(f"{self.base_url}/api/overview", timeout=5)
            response.raise_for_status()
            data = response.json()
            self.after(0, lambda: self._render(data))
        except (requests.RequestException, ValueError) as exc:
            self.after(0, lambda: self._show_error(str(exc)))

    def _render(self, data: dict) -> None:
        for child in self.cards.winfo_children():
            child.destroy()
        services = data.get("services", [])
        healthy = sum(item.get("status") == "healthy" for item in services)
        self.state_label.configure(text=f"{healthy}/{len(services)} 服务正常")
        self.summary.configure(text=f"共 {len(services)} 个企业项目 · 正常 {healthy} · 异常 {len(services) - healthy}")
        for index, service in enumerate(services):
            row, column = divmod(index, 3)
            card = ttk.Frame(self.cards, style="Panel.TFrame", padding=18)
            card.grid(row=row, column=column, sticky="nsew", padx=7, pady=7)
            self.cards.columnconfigure(column, weight=1, uniform="service")
            status = service.get("status") == "healthy"
            ttk.Label(card, text="运行正常" if status else "暂不可用", style="Healthy.TLabel" if status else "Down.TLabel").pack(anchor="w")
            ttk.Label(card, text=service.get("name", "企业项目"), style="CardTitle.TLabel").pack(anchor="w", pady=(16, 6))
            ttk.Label(card, text=service.get("description", ""), style="CardBody.TLabel", wraplength=290).pack(anchor="w")
            governance = f"{service.get('category', '企业应用')} · {service.get('tier', 'P3')} · SLO {service.get('slo', '-')}%"
            ttk.Label(card, text=governance, style="CardBody.TLabel").pack(anchor="w", pady=(12, 2))
            ttk.Label(card, text=f"责任团队：{service.get('owner', '未配置')} · {service.get('latency_ms', 0)} ms", style="CardBody.TLabel").pack(anchor="w", pady=(2, 4))
            ttk.Button(card, text="进入系统", command=lambda url=service.get("url", self.base_url): webbrowser.open(url)).pack(anchor="w", pady=(12, 0))

    def _show_error(self, detail: str) -> None:
        self.state_label.configure(text="门户连接失败")
        self.summary.configure(text="请检查本地 Docker 服务或服务器地址配置")
        messagebox.showwarning("SM Fusion Platform", f"融合门户暂不可用。\n\n{detail}")

    def _check_update(self) -> None:
        try:
            response = requests.get(LATEST_RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": f"SM-Fusion-Desktop/{DESKTOP_VERSION}"}, timeout=5)
            response.raise_for_status()
            latest = str(response.json().get("tag_name", "")).lstrip("v")
            if version_tuple(latest) > version_tuple(DESKTOP_VERSION):
                self.after(0, lambda: self.update_button.configure(text=f"发现 v{latest}"))
            else:
                self.after(0, lambda: self.update_button.configure(text="已是最新版"))
        except (requests.RequestException, ValueError, TypeError):
            self.after(0, lambda: self.update_button.configure(text="发布页"))


def version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("invalid semantic version")
    return tuple(int(part) for part in parts)


def main() -> int:
    FusionDesktop().mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
