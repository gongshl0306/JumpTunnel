"""SSH 端口转发 GUI 工具入口。

通过跳板机把目标 host:port 映射到本地端口，自动或指定本地端口，
生成可点击的本地 URL。等价于多条独立的 `ssh -N -L ...` 命令。

运行：python main.py
"""

import threading
import webbrowser
from typing import Dict, List, Optional

import customtkinter as ctk
from tkinter import messagebox

import config_store as cs
from tunnel_manager import MappingTunnel, TunnelError

# ---------- 外观配置 ----------
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 状态指示灯颜色
COLOR_RUNNING = "#2ecc71"   # 绿
COLOR_STOPPED = "#7f8c8d"   # 灰
COLOR_ERROR = "#e74c3c"     # 红

# 下拉框（OptionMenu）配色：深色底，比默认蓝柔和
MENU_BG         = "#3a3d42"   # 主体底色：深灰
MENU_BG_DARK    = "#2c2e33"   # 右侧按钮底色
MENU_BG_DARKER  = "#232529"   # 按钮 hover

# 全局字体：UI 用 Noto Sans SC（清爽现代），等宽内容用 Cascadia Code。
# 用元组而非 CTkFont，避免在模块顶层（无 root 窗口时）实例化字体。
F_UI        = ("Noto Sans SC", 13)
F_TITLE     = ("Noto Sans SC", 15, "bold")
F_SECTION   = ("Noto Sans SC", 13, "bold")
F_SUB       = ("Noto Sans SC", 12)   # 次要文字（目标信息）
F_STATUS    = ("Noto Sans SC", 16)   # 状态圆点
F_MENU      = ("Noto Sans SC", 13)   # 下拉框
F_MONO      = ("Cascadia Code", 12)  # 等宽：URL/命令/日志

# 协议默认推断：常见 https 端口
HTTPS_PORTS = {"443", "8443"}

# 常见 tcp 服务端口 -> 协议：用于自动推断非 Web 端口
TCP_SERVICE_PORTS = {
    "22": "ssh",
    "3306": "mysql",
    "6379": "redis",
    "5432": "postgres",
    "27017": "mongodb",
    "1433": "mssql",
    "1521": "oracle",
    "9092": "kafka",
    "5672": "rabbitmq",
    "8500": "consul",
}

# 各 tcp 服务对应的本地连接命令模板（{port} 占位）
# http/https 不在此表，它们用浏览器打开
TCP_COMMAND_TEMPLATES = {
    "ssh": "ssh {user}@localhost -p {port}",
    "mysql": "mysql -h localhost -P {port} -u root -p",
    "redis": "redis-cli -h localhost -p {port}",
    "postgres": 'psql -h localhost -p {port} -U postgres',
    "mongodb": "mongosh --host localhost --port {port}",
    "mssql": "sqlcmd -S localhost,{port} -U sa",
    "oracle": "sqlplus user/pass@localhost:{port}/ORCL",
    "kafka": "",   # kafka 无简单单行命令，仅显示连接串
    "rabbitmq": "",  # 同上
    "consul": "",    # 同上
    "tcp": "",       # 通用 tcp，仅显示 host:port
}


class MappingRow(ctk.CTkFrame):
    """活动映射列表中的一行。持有 UI 与对应的隧道对象。"""

    def __init__(self, master, mapping: Dict, app: "App"):
        super().__init__(master, fg_color=("gray90", "gray17"), corner_radius=8)
        self.mapping = mapping          # {auto_port, local_port, target_host, target_port, scheme, note}
        self.app = app
        self.tunnel: Optional[MappingTunnel] = None

        # ---------- 左侧：状态灯 + 本地 URL（可点击） + 目标信息 ----------
        self.left = ctk.CTkFrame(self, fg_color="transparent")
        self.left.pack(side="left", fill="x", expand=True, padx=(10, 5), pady=8)

        top_line = ctk.CTkFrame(self.left, fg_color="transparent")
        top_line.pack(fill="x")

        self.status_dot = ctk.CTkLabel(top_line, text="●", text_color=COLOR_STOPPED,
                                       font=F_STATUS)
        self.status_dot.pack(side="left", padx=(0, 8))

        self.url_label = ctk.CTkLabel(
            top_line, text=self._local_url(), text_color="#3498db",
            cursor="hand2", anchor="w", font=F_MONO,
        )
        self.url_label.pack(side="left", fill="x", expand=True)
        # 点击链接的行为：http/https 打开浏览器，tcp 复制命令
        self.url_label.bind("<Button-1>", lambda e: self._on_url_click())

        bot_line = ctk.CTkFrame(self.left, fg_color="transparent")
        bot_line.pack(fill="x", pady=(2, 0))
        target_text = f"→ {mapping['target_host']}:{mapping['target_port']}"
        if mapping.get("note"):
            target_text += f"   |   {mapping['note']}"
        self.target_label = ctk.CTkLabel(
            bot_line, text=target_text, text_color=("gray40", "gray60"),
            anchor="w", font=F_SUB,
        )
        self.target_label.pack(side="left")

        # ---------- 右侧：操作按钮 ----------
        self.btns = ctk.CTkFrame(self, fg_color="transparent")
        self.btns.pack(side="right", padx=(5, 10), pady=8)

        # 复制按钮：复制 URL / 命令到剪贴板（tcp 与 web 都有用）
        self.copy_btn = ctk.CTkButton(self.btns, text="复制", width=60,
                                      command=self.copy_to_clipboard)
        self.copy_btn.pack(side="left", padx=3)
        # 打开按钮：web 用浏览器打开；tcp 时改为复制命令，无独立打开语义
        self.open_btn = ctk.CTkButton(self.btns, text="打开", width=60,
                                      command=self.open_url)
        self.open_btn.pack(side="left", padx=3)

        self.toggle_btn = ctk.CTkButton(self.btns, text="启动", width=60,
                                        command=self.toggle)
        self.toggle_btn.pack(side="left", padx=3)

        self.del_btn = ctk.CTkButton(self.btns, text="删除", width=60,
                                     fg_color="#c0392b", hover_color="#922b21",
                                     command=self.delete)
        self.del_btn.pack(side="left", padx=3)

        self._refresh_ui()

    # ---------- UI 辅助 ----------

    def _resolved_port(self):
        """当前生效的本地端口（已启动则用实际端口，否则用配置的指定端口）。"""
        if self.tunnel and self.tunnel.actual_local_port:
            return self.tunnel.actual_local_port
        if not self.mapping.get("auto_port", False):
            return self.mapping.get("local_port", 0)
        return None

    def _is_web_scheme(self) -> bool:
        return self.mapping.get("scheme", "http") in ("http", "https")

    def _local_url(self) -> str:
        """根据当前状态生成本地 URL / 连接命令字符串。"""
        scheme = self.mapping.get("scheme", "http")
        port = self._resolved_port()

        # ---------- Web 协议：给浏览器 URL ----------
        if scheme in ("http", "https"):
            if not port:
                return f"{scheme}://localhost:（待启动，自动分配端口）"
            if (scheme == "http" and port == 80) or (scheme == "https" and port == 443):
                return f"{scheme}://localhost"
            return f"{scheme}://localhost:{port}"

        # ---------- tcp 协议：给连接命令 ----------
        if not port:
            return f"localhost:（待启动，自动分配端口）  [{scheme}]"
        # 有模板的服务：填入本地用户与端口生成命令
        tmpl = TCP_COMMAND_TEMPLATES.get(scheme, "localhost:{port}")
        if tmpl == "":
            return f"localhost:{port}  [{scheme}]"
        try:
            return tmpl.format(port=port, user=self.app.current_jumphost_user())
        except (KeyError, IndexError):
            return tmpl.format(port=port)

    def _refresh_ui(self) -> None:
        """根据隧道状态刷新本行显示。"""
        active = self.tunnel is not None and self.tunnel.is_active()
        if active:
            self.status_dot.configure(text_color=COLOR_RUNNING)
            self.toggle_btn.configure(text="停止", fg_color="#e67e22", hover_color="#d35400")
        elif self.tunnel is not None and getattr(self.tunnel, "_errored", False):
            self.status_dot.configure(text_color=COLOR_ERROR)
            self.toggle_btn.configure(text="启动", fg_color="#27ae60", hover_color="#229954")
        else:
            self.status_dot.configure(text_color=COLOR_STOPPED)
            self.toggle_btn.configure(text="启动", fg_color="#27ae60", hover_color="#229954")
        self.url_label.configure(text=self._local_url())
        # tcp/非 web 协议隐藏「打开」按钮（无浏览器语义），保留「复制」
        if self._is_web_scheme():
            self.open_btn.pack(side="left", padx=3)
        else:
            self.open_btn.pack_forget()

    # ---------- 操作 ----------

    def _on_url_click(self) -> None:
        """点击链接：web 打开浏览器，tcp 复制命令。"""
        if self._is_web_scheme():
            self.open_url()
        else:
            self.copy_to_clipboard()

    def open_url(self) -> None:
        """web 协议：在浏览器打开本地 URL。"""
        if not self._is_web_scheme():
            self.app.log("该映射为 tcp 协议，无法用浏览器打开，已改用复制")
            self.copy_to_clipboard()
            return
        url = self._local_url()
        if "待启动" in url:
            self.app.log("请先启动该映射再打开 URL")
            return
        webbrowser.open(url)
        self.app.log(f"已在浏览器打开：{url}")

    def copy_to_clipboard(self) -> None:
        """复制当前 URL / 连接命令到剪贴板。"""
        text = self._local_url()
        if "待启动" in text:
            self.app.log("请先启动该映射再复制")
            return
        self.app.clipboard_clear()
        self.app.clipboard_append(text)
        self.app.log(f"已复制到剪贴板：{text}")

    def toggle(self) -> None:
        """启动或停止隧道（后台线程，避免阻塞 UI）。"""
        if self.tunnel is not None and self.tunnel.is_active():
            self._stop_async()
        else:
            self._start_async()

    def _start_async(self) -> None:
        self.app.log(f"正在建立隧道 -> {self.mapping['target_host']}:{self.mapping['target_port']}")

        def work():
            jump = self.app.get_jumphost()
            if jump is None:
                return
            try:
                self.tunnel = MappingTunnel(
                    jumphost=jump["host"], jumpport=jump["port"],
                    username=jump["username"], password=jump["password"],
                    target_host=self.mapping["target_host"],
                    target_port=int(self.mapping["target_port"]),
                    local_port=int(self.mapping["local_port"]) if not self.mapping.get("auto_port") else 0,
                )
                port = self.tunnel.start()
                self.tunnel._errored = False
                self.app.log(f"隧道已建立：{self.tunnel.info()}")
            except TunnelError as e:
                if self.tunnel is not None:
                    self.tunnel._errored = True
                self.app.log(f"隧道建立失败：{e}")
            except Exception as e:  # noqa
                self.app.log(f"未知错误：{e}")
            finally:
                # 回到主线程刷新 UI
                self.after(0, self._refresh_ui)
                self.after(0, self.app.refresh_all_rows)

        threading.Thread(target=work, daemon=True).start()

    def _stop_async(self) -> None:
        def work():
            if self.tunnel is not None:
                info = self.tunnel.info()
                self.tunnel.stop()
                self.app.log(f"隧道已停止：{info}")
            self.after(0, self._refresh_ui)
            self.after(0, self.app.refresh_all_rows)

        threading.Thread(target=work, daemon=True).start()

    def stop(self) -> None:
        """供「全部停止」/ 退出调用：同步停止。"""
        if self.tunnel is not None:
            try:
                self.tunnel.stop()
            except Exception:
                pass

    def delete(self) -> None:
        self.stop()
        self.app.remove_row(self)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SSH 端口转发工具")
        self.geometry("820x720")
        self.minsize(760, 600)

        self.config = cs.load_config()
        self.rows: List[MappingRow] = []

        self._build_jumphost_section()
        self._build_new_mapping_section()
        self._build_mappings_section()
        self._build_log_section()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._restore_mappings()

    # ---------- 跳板机配置区 ----------

    def _build_jumphost_section(self) -> None:
        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=12, pady=(12, 6))

        ctk.CTkLabel(box, text="跳板机配置",
                     font=F_TITLE).pack(
                         anchor="w", padx=12, pady=(10, 4))

        # 第一行：档案下拉 + 增删按钮
        row1 = ctk.CTkFrame(box, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=4)

        self.profile_var = ctk.StringVar(value=self.config.get("last_profile", ""))
        self.profile_menu = ctk.CTkOptionMenu(
            row1, variable=self.profile_var, values=cs.profile_names(self.config),
            command=self._on_profile_selected, width=200, height=32,
            fg_color=MENU_BG, button_color=MENU_BG_DARK, button_hover_color=MENU_BG_DARKER,
            text_color="#ffffff", dropdown_fg_color=MENU_BG,
            dropdown_hover_color=MENU_BG_DARK, dropdown_text_color="#ffffff",
            corner_radius=8, font=F_MENU, dropdown_font=F_MENU,
        )
        self.profile_menu.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(row1, text="档案").pack(side="left", padx=(0, 6))

        ctk.CTkButton(row1, text="另存为新档案", width=110,
                      command=self._save_as_new).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="覆盖保存", width=90,
                      command=self._overwrite_save).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="删除档案", width=90, fg_color="#c0392b",
                      hover_color="#922b21",
                      command=self._delete_profile).pack(side="left", padx=4)
        ctk.CTkButton(row1, text="测试连接", width=90,
                      command=self._test_connection).pack(side="right", padx=4)

        # 第二行：主机/端口/用户/密码
        row2 = ctk.CTkFrame(box, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 12))

        ctk.CTkLabel(row2, text="主机").pack(side="left")
        self.host_entry = ctk.CTkEntry(row2, width=170, placeholder_text="如 10.0.0.1")
        self.host_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(row2, text="端口").pack(side="left")
        self.port_entry = ctk.CTkEntry(row2, width=60, placeholder_text="22")
        self.port_entry.insert(0, "22")
        self.port_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(row2, text="用户名").pack(side="left")
        self.user_entry = ctk.CTkEntry(row2, width=120, placeholder_text="root")
        self.user_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(row2, text="密码").pack(side="left")
        self.pwd_entry = ctk.CTkEntry(row2, width=160, show="*", placeholder_text="password")
        self.pwd_entry.pack(side="left", padx=(4, 0))

        # 恢复上次选中的档案到输入框
        if self.config.get("last_profile"):
            self._load_profile_to_entries(self.config["last_profile"])

    def _on_profile_selected(self, name: str) -> None:
        self._load_profile_to_entries(name)
        self.config["last_profile"] = name
        cs.save_config(self.config)

    def _load_profile_to_entries(self, name: str) -> None:
        p = cs.find_profile(self.config, name)
        if not p:
            return
        self.host_entry.delete(0, "end"); self.host_entry.insert(0, p.get("host", ""))
        self.port_entry.delete(0, "end"); self.port_entry.insert(0, str(p.get("port", 22)))
        self.user_entry.delete(0, "end"); self.user_entry.insert(0, p.get("username", ""))
        self.pwd_entry.delete(0, "end"); self.pwd_entry.insert(0, p.get("password", ""))

    def _read_jumphost_from_entries(self) -> Optional[Dict]:
        """从输入框读取跳板机信息，校验失败返回 None。"""
        host = self.host_entry.get().strip()
        user = self.user_entry.get().strip()
        pwd = self.pwd_entry.get()
        port_s = self.port_entry.get().strip() or "22"
        if not host or not user:
            messagebox.showwarning("缺少信息", "请填写跳板机的主机和用户名")
            return None
        try:
            port = int(port_s)
        except ValueError:
            messagebox.showwarning("端口错误", "跳板机端口必须是整数")
            return None
        return {"host": host, "port": port, "username": user, "password": pwd}

    def _save_as_new(self) -> None:
        data = self._read_jumphost_from_entries()
        if data is None:
            return
        name = ctk.CTkInputDialog(  # type: ignore
            text="请输入档案名称：", title="另存为新档案").get_input()
        if not name:
            return
        if name in cs.profile_names(self.config):
            if not messagebox.askyesno("重名", f"档案「{name}」已存在，是否覆盖？"):
                return
        cs.upsert_profile(self.config, {
            "name": name, "host": data["host"], "port": data["port"],
            "username": data["username"], "password": data["password"],
        })
        self.config["last_profile"] = name
        cs.save_config(self.config)
        self._refresh_profile_menu()
        self.profile_var.set(name)
        self.log(f"已保存档案：{name}")

    def _overwrite_save(self) -> None:
        data = self._read_jumphost_from_entries()
        if data is None:
            return
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("提示", "当前没有选中档案，请用「另存为新档案」")
            return
        cs.upsert_profile(self.config, {
            "name": name, "host": data["host"], "port": data["port"],
            "username": data["username"], "password": data["password"],
        })
        cs.save_config(self.config)
        self.log(f"已覆盖保存档案：{name}")

    def _delete_profile(self) -> None:
        name = self.profile_var.get()
        if not name:
            return
        if not messagebox.askyesno("确认", f"删除档案「{name}」？"):
            return
        cs.delete_profile(self.config, name)
        cs.save_config(self.config)
        self._refresh_profile_menu()
        self.profile_var.set("")
        self.log(f"已删除档案：{name}")

    def _refresh_profile_menu(self) -> None:
        names = cs.profile_names(self.config)
        self.profile_menu.configure(values=names)

    def _test_connection(self) -> None:
        data = self._read_jumphost_from_entries()
        if data is None:
            return
        self.log(f"测试连接 {data['host']}:{data['port']} ...")

        def work():
            try:
                # 直接用 paramiko 做一次连接握手即可
                import paramiko
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(data["host"], port=data["port"],
                               username=data["username"],
                               password=data["password"], timeout=8)
                client.close()
                self.log("连接成功 ✓")
            except Exception as e:
                self.log(f"连接失败：{e}")

        threading.Thread(target=work, daemon=True).start()

    # ---------- 新增映射区 ----------

    def _build_new_mapping_section(self) -> None:
        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=12, pady=6)

        ctk.CTkLabel(box, text="新增映射",
                     font=F_TITLE).pack(
                         anchor="w", padx=12, pady=(10, 4))

        # 第一行：目标 IP / 端口 / 协议 / 添加按钮（核心字段，保证小窗口下也可见）
        row1 = ctk.CTkFrame(box, fg_color="transparent")
        row1.pack(fill="x", padx=12, pady=(4, 4))

        ctk.CTkLabel(row1, text="目标IP").pack(side="left")
        self.target_host_entry = ctk.CTkEntry(row1, width=150, placeholder_text="如 172.17.12.22")
        self.target_host_entry.pack(side="left", padx=(4, 10))

        ctk.CTkLabel(row1, text="目标端口").pack(side="left")
        self.target_port_entry = ctk.CTkEntry(row1, width=64, placeholder_text="443")
        self.target_port_entry.bind("<KeyRelease>", self._auto_guess_scheme)
        self.target_port_entry.pack(side="left", padx=(4, 10))

        ctk.CTkLabel(row1, text="协议").pack(side="left")
        self.scheme_menu = ctk.CTkOptionMenu(
            row1, values=["http", "https", "tcp",
                          "ssh", "mysql", "redis", "postgres", "mongodb"],
            width=104, height=32,
            fg_color=MENU_BG, button_color=MENU_BG_DARK, button_hover_color=MENU_BG_DARKER,
            text_color="#ffffff", dropdown_fg_color=MENU_BG,
            dropdown_hover_color=MENU_BG_DARK, dropdown_text_color="#ffffff",
            corner_radius=8, font=F_MENU, dropdown_font=F_MENU,
        )
        self.scheme_menu.set("http")
        self.scheme_menu.pack(side="left", padx=(4, 0))

        ctk.CTkButton(row1, text="＋ 添加映射", width=110,
                      command=self._add_mapping).pack(side="right")

        # 第二行：本地端口 / 备注（次要字段，单独一行）
        row2 = ctk.CTkFrame(box, fg_color="transparent")
        row2.pack(fill="x", padx=12, pady=(4, 12))

        self.auto_port_var = ctk.BooleanVar(value=True)
        self.auto_chk = ctk.CTkCheckBox(row2, text="自动端口", variable=self.auto_port_var,
                                        command=self._toggle_local_port)
        self.auto_chk.pack(side="left", padx=(0, 8))

        ctk.CTkLabel(row2, text="本地端口").pack(side="left")
        self.local_port_entry = ctk.CTkEntry(row2, width=70, placeholder_text="留空=自动")
        self.local_port_entry.configure(state="disabled")
        self.local_port_entry.pack(side="left", padx=(4, 12))

        ctk.CTkLabel(row2, text="备注").pack(side="left")
        self.note_entry = ctk.CTkEntry(row2, width=200, placeholder_text="可选")
        self.note_entry.pack(side="left", padx=(4, 12))

    def _toggle_local_port(self) -> None:
        if self.auto_port_var.get():
            self.local_port_entry.delete(0, "end")
            self.local_port_entry.configure(state="disabled")
        else:
            self.local_port_entry.configure(state="normal")

    def _auto_guess_scheme(self, _evt=None) -> None:
        """根据目标端口自动推断协议。

        Web 端口 -> http/https；已知 tcp 服务端口 -> 对应服务名；
        其它 -> tcp（通用）。
        """
        p = self.target_port_entry.get().strip()
        if not p:
            return
        if p in HTTPS_PORTS:
            self.scheme_menu.set("https")
        elif p in {"80", "8080", "8000"}:
            self.scheme_menu.set("http")
        elif p in TCP_SERVICE_PORTS:
            svc = TCP_SERVICE_PORTS[p]
            # 只在下拉菜单里有该服务名时才选它，否则回退 tcp
            if svc in self.scheme_menu.cget("values"):
                self.scheme_menu.set(svc)
            else:
                self.scheme_menu.set("tcp")
        else:
            self.scheme_menu.set("tcp")

    def _add_mapping(self) -> None:
        th = self.target_host_entry.get().strip()
        tp = self.target_port_entry.get().strip()
        if not th or not tp:
            messagebox.showwarning("缺少信息", "请填写目标 IP 和目标端口")
            return
        try:
            tp_i = int(tp)
        except ValueError:
            messagebox.showwarning("端口错误", "目标端口必须是整数")
            return

        if self.auto_port_var.get():
            local_port = 0
        else:
            lp = self.local_port_entry.get().strip()
            try:
                local_port = int(lp) if lp else 0
            except ValueError:
                messagebox.showwarning("端口错误", "本地端口必须是整数")
                return

        mapping = {
            "auto_port": self.auto_port_var.get(),
            "local_port": local_port,
            "target_host": th,
            "target_port": tp_i,
            "scheme": self.scheme_menu.get(),
            "note": self.note_entry.get().strip(),
        }
        self._append_row(mapping)
        self._persist_mappings()
        # 清空目标输入，方便连续添加
        self.target_host_entry.delete(0, "end")
        self.target_port_entry.delete(0, "end")
        self.note_entry.delete(0, "end")

    # ---------- 活动映射区 ----------

    def _build_mappings_section(self) -> None:
        box = ctk.CTkFrame(self)
        box.pack(fill="both", expand=True, padx=12, pady=6)

        header = ctk.CTkFrame(box, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))
        ctk.CTkLabel(header, text="活动映射",
                     font=F_TITLE).pack(side="left")
        ctk.CTkButton(header, text="全部启动", width=90, fg_color="#27ae60",
                      hover_color="#229954",
                      command=self._start_all).pack(side="right", padx=4)
        ctk.CTkButton(header, text="全部停止", width=90, fg_color="#e67e22",
                      hover_color="#d35400",
                      command=self._stop_all).pack(side="right", padx=4)

        # 可滚动容器
        self.scroll = ctk.CTkScrollableFrame(box, label_text="")
        self.scroll.pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def _append_row(self, mapping: Dict) -> MappingRow:
        row = MappingRow(self.scroll, mapping, self)
        row.pack(fill="x", padx=4, pady=4)
        self.rows.append(row)
        return row

    def remove_row(self, row: MappingRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
        row.destroy()
        self._persist_mappings()
        self.log("已删除该映射")

    def refresh_all_rows(self) -> None:
        for r in self.rows:
            r._refresh_ui()

    def _start_all(self) -> None:
        for r in self.rows:
            if not (r.tunnel and r.tunnel.is_active()):
                r._start_async()

    def _stop_all(self) -> None:
        for r in self.rows:
            if r.tunnel and r.tunnel.is_active():
                r._stop_async()

    # ---------- 日志区 ----------

    def _build_log_section(self) -> None:
        box = ctk.CTkFrame(self)
        box.pack(fill="x", padx=12, pady=(6, 12))
        ctk.CTkLabel(box, text="日志",
                     font=F_SECTION).pack(
                         anchor="w", padx=12, pady=(8, 2))
        self.log_box = ctk.CTkTextbox(box, height=90, state="disabled",
                                      font=F_MONO)
        self.log_box.pack(fill="x", padx=12, pady=(0, 10))

    def log(self, msg: str) -> None:
        """线程安全地追加日志。"""
        def _do():
            self.log_box.configure(state="normal")
            self.log_box.insert("end", msg + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        # 在主线程执行
        try:
            self.after(0, _do)
        except RuntimeError:
            pass  # 窗口已关闭

    # ---------- 公共辅助 ----------

    def get_jumphost(self) -> Optional[Dict]:
        """供行对象获取跳板机信息（带校验）。"""
        return self._read_jumphost_from_entries()

    def current_jumphost_user(self) -> str:
        """供生成 tcp 连接命令时取用户名（用于 ssh 等命令）。"""
        return self.user_entry.get().strip() or "root"

    # ---------- 持久化与生命周期 ----------

    def _persist_mappings(self) -> None:
        cs.set_last_mappings(self.config, [r.mapping for r in self.rows])
        cs.save_config(self.config)

    def _restore_mappings(self) -> None:
        for m in self.config.get("last_mappings", []):
            self._append_row(dict(m))  # 拷贝，避免互相影响

    def _on_close(self) -> None:
        """退出前停止所有隧道并保存。"""
        for r in self.rows:
            r.stop()
        self._persist_mappings()
        self.destroy()


def main() -> None:
    """程序入口：供脚本入口 / 打包 / 直接运行统一调用。"""
    App().mainloop()


if __name__ == "__main__":
    main()
