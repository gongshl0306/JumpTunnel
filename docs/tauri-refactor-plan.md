# JumpTunnel 重构计划：Python/CustomTkinter → Rust + Tauri 2

> 目标：轻量化 + 高性能 + 现代化前端。
> 本文档为重构实施方案，评审通过后按阶段执行，每阶段结束都有可运行、可验证的产物。

---

## 1. 结论先行

**可行，且收益明确。** JumpTunnel 是典型的「轻后端 + 单窗口工具型 GUI」，正好落在 Tauri 的最佳适用区间：

| 维度 | 现状（Python + CustomTkinter + sshtunnel） | 重构后（Rust + Tauri 2 + Web 前端） |
|------|------|------|
| 分发体积 | ~15 MB 单文件 exe（自解压） | 预计 5~8 MB，无需解压 |
| 启动速度 | 1~2 s（PyInstaller 自解压） | < 0.5 s |
| SSH 引擎 | paramiko/sshtunnel（解释执行，线程模型） | russh（纯 Rust + tokio 异步） |
| UI | Tk 画布手绘，需大量「防重绘 hack」 | HTML/CSS 现代组件，浏览器级渲染 |
| 健壮性 | 动态类型，线程回调散落 `after(0)` hack | 静态类型 + 编译期检查 + 事件驱动 |
| 老代码痛点 | `main.py` 里 `_set_if_changed`、日志合并缓冲、防重入标志，全是在给 Tkinter 擦屁股 | 全部消失：前端 diff 渲染，后端 emit 事件 |

**一个诚实的取舍**：WebView2 的内存占用（约 60~100 MB）大概率高于 Tkinter（约 40~50 MB）。「轻量化」体现在**分发体积和启动速度**，不在内存；换来的是现代化 UI 和长期开发效率。工具类应用这个取舍通常是划算的。

---

## 2. 技术选型

### 2.1 SSH 库（核心决策）：russh

| 选项 | 评价 |
|------|------|
| **russh**（选用） | 纯 Rust、tokio 异步、支持密码认证与 direct-tcpip 通道。与 Tauri 的异步运行时天然一致，无 C 编译链依赖，Windows 交叉构建零烦恼。需要自己实现本地转发循环（`TcpListener` → `direct-tcpip` 通道 → 双向拷贝），是社区成熟模式，约 100~150 行。 |
| ssh2（libssh2 绑定） | 阻塞式 API，转发 API 更省事，但引入 C 依赖（Windows 需 cmake），与 tokio 生态不搭。**作为 russh 受阻时的备选。** |
| 调用系统 ssh.exe | 不可行。Windows OpenSSH 不接受命令行明文密码——这正是当初弃用 ssh.exe 改用 sshtunnel 的原因。 |

需要显式对齐的现状行为：
- 密码认证（`russh::client::Auth` + `auth_password`）。
- Host key 不校验（对齐 paramiko 的 `AutoAddPolicy`；在 README 中保留同样的安全提示）。
- keepalive 30 s（russh `Config::keepalive_interval`）。
- 本地端口 `0` 由操作系统分配，启动后读回实际端口（`TcpListener.local_addr()`）。

### 2.2 前端：React 18 + TypeScript + Vite + Tailwind CSS + shadcn/ui

- **React**：组件生态最全（shadcn/ui 提供现成的现代暗色主题组件），AI 辅助开发的语料最足，出问题最好查。
- **Tailwind + shadcn/ui**：深色卡片、圆角、状态徽章、动效都是现成的，直接达到「现代化」观感。
- 状态管理用 **zustand**（极轻），前后端通信走 Tauri 的 `invoke`（命令）+ `listen`（事件）。
- 备选：Svelte 5（产物更小，但组件生态弱）、Vue 3（同样可行）。体积差异在这个项目里不构成决策因素（几十 KB vs 数 MB exe），**生态和开发效率优先，故选 React**。

### 2.3 Tauri 2 生态

- `tauri-plugin-single-instance`：防止双开导致端口抢占。
- 系统托盘（Tauri 2 内置 tray-icon）：关闭最小化到托盘（可选增强）。
- `tauri-plugin-clipboard-manager` / `opener`：复制与打开浏览器（也可用后端 `arboard` + `open` crate，二选一，Phase 2 定）。
- 打包：`tauri build` → NSIS 安装包 + 免安装单 exe。

---

## 3. 目标架构

### 3.1 目录结构（同仓库过渡，不另开新 repo）

```
ZCodeProject/
├── src/jumptunnel/        # 旧 Python 版：过渡期保留作对照基准，验收后删除
├── frontend/              # 新前端（Vite + React + TS + Tailwind）
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/    # JumphostPanel / MappingForm / MappingRow / LogPanel
│   │   ├── stores/        # zustand: profiles, mappings, tunnels, logs
│   │   └── ipc.ts         # invoke/listen 封装与类型
│   └── package.json
├── src-tauri/             # Rust 后端
│   ├── src/
│   │   ├── main.rs        # 入口：窗口、托盘、插件注册
│   │   ├── commands.rs    # 全部 #[tauri::command]
│   │   ├── config.rs      # 配置读写 + 旧版迁移
│   │   ├── events.rs      # 前端事件定义
│   │   └── tunnel/
│   │       ├── mod.rs     # TunnelManager：隧道状态机与生命周期
│   │       └── forward.rs # russh：连接、认证、本地转发循环
│   ├── tauri.conf.json
│   └── Cargo.toml
├── docs/tauri-refactor-plan.md   # 本文档
└── (旧 pyproject.toml / build.spec 过渡期保留)
```

### 3.2 核心设计：后端是唯一事实源，事件驱动 UI

现状 Tkinter 版最大的结构性问题是「UI 组件直接持有隧道对象」，导致防重入、跨线程刷 UI、防重绘三套补丁。重构后彻底反转：

```
前端 (React)                         后端 (Rust)
┌─────────────┐    invoke(命令)     ┌──────────────────┐
│ 纯展示 + 意图 │ ──────────────────→ │ TunnelManager     │
│ 渲染         │                     │  ├─ per-mapping   │
│             │ ←────────────────── │  │   tokio task   │
└─────────────┘  emit(事件流)        │  └─ 状态机        │
                                    └──────────────────┘
```

- **隧道状态机**（每条映射一个）：
  `Stopped → Connecting → Running{actual_port} → (Stopped | Error{msg})`
  状态变化 → `emit("tunnel-status", { id, status })`。
- **日志**：后端统一日志通道 → `emit("log", { ts, level, msg })`。Tkinter 版的 80 ms 合并缓冲、400 行截断逻辑，前端用一个 ring buffer 即可，不再是后端包袱。
- 前端启动时 `invoke("get_initial_state")` 拉全量快照，之后完全由事件驱动，无需轮询。

### 3.3 Tauri IPC 面（命令清单）

```rust
// 配置
get_initial_state() -> AppState          // profiles + mappings + 各隧道状态
list_profiles() / save_profile(p) / delete_profile(name)
set_last_profile(name)
// 映射
add_mapping(m: MappingInput) -> Mapping  // 后端分配 id
update_mapping(m) / remove_mapping(id)
// 隧道
test_connection(j: Jumphost) -> Result<(), String>       // 8s 超时，翻译中文错误
start_tunnel(id) -> Result<u16, String>  // 返回实际本地端口（支持自动分配）
stop_tunnel(id) / start_all() / stop_all()
// 事件
"tunnel-status" { id, status }           // Stopped|Connecting|Running{port}|Error{msg}
"log" { ts, level, msg }
```

### 3.4 配置与迁移

- 新配置目录：Tauri `app_config_dir`（`%APPDATA%\com.jumptunnel.app\config.json`），schema 与旧版完全一致（profiles / last_mappings / last_profile），**旧文件可直接复用**。
- 首次启动检测旧路径 `~\.ssh_forward_tool\config.json` 存在 → 自动导入并备份。
- 密码明文存储的现状**在 Phase 1 保持不变**（迁移优先）；Phase 4 升级为 Windows 凭据管理器（`keyring` crate），旧明文字段做兼容读取。

---

## 4. 功能对照清单（验收基准）

来源：`src/jumptunnel/main.py` + `tunnel_manager.py` + `config_store.py`，重构必须全绿。

| # | 功能 | 现状行为 | 重构后 |
|---|------|---------|--------|
| 1 | 跳板机档案 | 下拉切换、另存为新、覆盖保存、删除，持久化 last_profile | 同左 |
| 2 | 测试连接 | 8 s 超时，错误翻译为中文（认证失败/超时/域名解析失败），按钮测试中禁用 | 同左 |
| 3 | 密码显隐 | 掩码/明文切换 | 同左 |
| 4 | 添加映射 | 目标 IP/端口校验；端口→协议自动推断（443/8443→https，80/8080/8000→http，22→ssh，3306→mysql，6379→redis，5432→postgres，27017→mongodb，1433→mssql，1521→oracle，9092→kafka，5672→rabbitmq，8500→consul，其余→tcp）；可手动改协议 | 同左（推断表进 Rust 常量 + 前端即时联动） |
| 5 | 本地端口 | 默认自动（绑 0 由系统分配，启动后回读实际端口）；可手动指定 | 同左 |
| 6 | 备注 | 可选，显示在映射行 | 同左 |
| 7 | 隧道启停 | 单条启停，连接中/断开中防重入；全部启动/全部停止 | 同左（状态机天然解决防重入） |
| 8 | 状态指示 | 🟢运行 / ⚪停止 / 🔴出错 | 同左（状态徽章） |
| 9 | Web 协议 | 生成 `http(s)://localhost[:port]`，点击/「打开」调浏览器 | 同左 |
| 10 | tcp 协议 | 生成连接命令模板（`ssh {user}@localhost -p {port}`、mysql/redis/psql/mongosh/sqlcmd/sqlplus…），复制到剪贴板；隐藏「打开」按钮 | 同左 |
| 11 | 错误翻译 | 认证失败/超时/域名解析/端口占用/目标不可达 → 中文提示 | 同左（集中在 Rust 一处） |
| 12 | 日志面板 | 时间序追加，上限 400 行截断 | 同左（前端 ring buffer） |
| 13 | 持久化 | 增删映射/切档案即写盘；退出时保存映射列表 | 同左（写盘集中在后端） |
| 14 | keepalive | 30 s | 同左 |
| 15 | 窗口 | 820×720，min 760×600，暗色主题，应用图标 | 同左 + 深浅色切换（增强） |
| 16 | 退出清理 | 后台停所有隧道，3 s 兜底强制退出 | 同左（tauri 退出钩子 + tokio 超时） |

Phase 4 可选增强（不阻塞验收）：关闭最小化到托盘、单实例、断连自动重连、密码入凭据管理器、隧道流量统计。

---

## 5. 分阶段实施

### Phase 0：脚手架（0.5 天）
- `cargo tauri init`（或手写脚手架），目录结构按 §3.1。
- 前端 Vite + React + TS + Tailwind + shadcn/ui 跑通 `dev` 与 `build`。
- `tauri.conf.json`：窗口尺寸、图标（复用 `docs/logo.ico`）、标识符 `com.jumptunnel.app`。
- **产物**：空壳应用窗口能启动。

### Phase 1：Rust 核心域（2~3 天，无 UI 依赖）
- `config.rs`：读写 + 容错 + 旧配置自动导入。
- `tunnel/forward.rs`：russh 连接、密码认证、`direct-tcpip` 本地转发循环、keepalive、自动端口。
- `tunnel/mod.rs`：TunnelManager 状态机（HashMap<id, Handle>，状态 watch 通道）。
- 错误翻译模块（对齐 §4 #11 的五类中文提示）。
- **验证**：`cargo test` + 一个针对真实跳板机的集成测试脚本（连上→转发→curl 通→断开）。此阶段风险最高，尽早做。
- **产物**：`cargo run --example tunnel_demo` 命令行即可建/停隧道。

### Phase 2：IPC 接线 + 前端骨架（1~2 天）
- `commands.rs` / `events.rs` 全量命令与事件。
- 前端：App 布局（跳板机区 / 新增映射区 / 映射列表 / 日志区，对齐现有信息架构）、主题、zustand store、ipc 封装、事件订阅。
- **产物**：空数据流的完整界面壳。

### Phase 3：功能对齐（2~3 天）
- 按 §4 清单逐项实现并打勾：档案 CRUD → 映射 CRUD → 启停 → Web/tcp 分支 → 日志 → 持久化 → 退出清理。
- 新旧版本并行运行做对照测试（同一跳板机、同一批映射）。
- **产物**：功能对齐清单全绿。

### Phase 4：打磨与打包（1~2 天）
- 单实例、托盘（可选）、深浅色切换、断连状态自动标记。
- `tauri build` 出 NSIS 安装包 + 便携 exe；确认杀软不误报。
- 空图标/资源、版本号、README 更新。
- **产物**：可分发的 exe。

### Phase 5：切换与收尾（0.5~1 天）
- 干净 Win11 机器验证：无 Rust/Python/Node 环境，双击运行，旧配置自动导入。
- 观察期（建议 3~5 天日常使用）后删除 `src/jumptunnel/`、`build.spec`、`requirements.txt` 等 Python 资产，README 换血。

**合计约 7~11 个工作日**（风险集中在 Phase 1 的 russh 转发实现）。

---

## 6. 风险与对策

| 风险 | 等级 | 对策 |
|------|------|------|
| russh 本地转发的生命周期细节（连接清理、错误传播、半开连接） | **高** | 独立模块 + 真实跳板机集成测试前置到 Phase 1；长期运行 30 min 稳定性测试（10 条并发映射）；实在受阻降级 ssh2 crate（API 更直接，代价是 C 依赖） |
| WebView2 运行时依赖 | 低 | Win10 1803+/Win11 内置；Tauri 安装包自带 bootstrapper |
| 内存占用高于 Tkinter | 低（已知取舍） | §1 已声明；工具类应用可接受 |
| Host key 不校验的安全面 | 低（与现状一致） | 行为对齐 + README 保留提示；后续版本可加 known_hosts 支持 |
| 杀软误报 | 低 | Tauri 比 PyInstaller 单文件误报率低；必要时代码签名 |

---

## 7. 预期收益（验收时核对）

- 分发体积 15 MB → **≤ 8 MB**，启动 1~2 s → **< 0.5 s**。
- 隧道引擎从「每映射一线程的 paramiko」→ **tokio 异步**，并发连接与长连接稳定性上一个台阶。
- UI 达到现代桌面应用观感（暗色卡片、状态徽章、动效、深浅色切换），且**删除** Tkinter 版全部三类补丁代码（防重绘 / 日志合并 / 线程回主线程）。
- 前后端类型贯通（TS 类型 ↔ serde 结构体），配置/状态类 bug 编译期暴露。
