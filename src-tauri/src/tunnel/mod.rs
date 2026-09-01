//! 隧道管理器：每条映射一个 tokio 任务，维护状态机，
//! 状态变化通过 Tauri 事件推给前端。

pub mod forward;

use std::collections::HashMap;
use std::sync::Mutex;

use serde::Serialize;
use tauri::{AppHandle, Emitter};

use crate::config::Mapping;
use forward::{ForwardHandle, Jumphost, start_forward};

/// 隧道状态（推给前端）
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase", tag = "state")]
pub enum TunnelStatus {
    Stopped,
    Connecting,
    Running {
        #[serde(rename = "actualPort")]
        actual_port: u16,
    },
    Error { message: String },
}

struct TunnelEntry {
    handle: Option<ForwardHandle>,
    status: TunnelStatus,
}

pub struct TunnelManager {
    app: Mutex<Option<AppHandle>>,
    entries: Mutex<HashMap<String, TunnelEntry>>,
}

impl TunnelManager {
    pub fn new() -> Self {
        Self {
            app: Mutex::new(None),
            entries: Mutex::new(HashMap::new()),
        }
    }

    /// 注入 AppHandle（在 setup 阶段调用），用于 emit 事件。
    pub fn set_app(&self, app: AppHandle) {
        *self.app.lock().unwrap() = Some(app);
    }

    fn emit_status(&self, id: &str, status: &TunnelStatus) {
        if let Some(app) = self.app.lock().unwrap().as_ref() {
            let _ = app.emit("tunnel-status", crate::events::TunnelStatusEvent {
                id: id.to_string(),
                status: status.clone(),
            });
        }
    }

    fn log(&self, msg: &str) {
        log::info!("{msg}");
        if let Some(app) = self.app.lock().unwrap().as_ref() {
            let _ = app.emit(
                "log",
                crate::events::LogEvent {
                    ts: chrono_now_ms(),
                    level: "info".into(),
                    msg: msg.to_string(),
                },
            );
        }
    }

    /// 当前所有隧道的状态快照（启动时给前端）。
    pub fn status_snapshot(&self) -> Vec<(String, TunnelStatus)> {
        self.entries
            .lock()
            .unwrap()
            .iter()
            .map(|(id, e)| (id.clone(), e.status.clone()))
            .collect()
    }

    /// 启动一条隧道。返回实际本地端口。
    pub async fn start(&self, id: &str, jump: &Jumphost, mapping: &Mapping) -> Result<u16, String> {
        {
            let mut entries = self.entries.lock().unwrap();
            let entry = entries.entry(id.to_string()).or_insert(TunnelEntry {
                handle: None,
                status: TunnelStatus::Stopped,
            });
            // 已在运行：直接返回
            if let TunnelStatus::Running { actual_port } = &entry.status {
                return Ok(*actual_port);
            }
            // 防重入：连接中忽略
            if matches!(entry.status, TunnelStatus::Connecting) {
                return Err("正在连接中，请稍候".into());
            }
            entry.status = TunnelStatus::Connecting;
        }
        self.emit_status(id, &TunnelStatus::Connecting);
        self.log(&format!(
            "正在建立隧道 -> {}:{}",
            mapping.target_host, mapping.target_port
        ));

        match start_forward(jump, mapping).await {
            Ok(handle) => {
                let port = handle.actual_local_port;
                let status = TunnelStatus::Running { actual_port: port };
                {
                    let mut entries = self.entries.lock().unwrap();
                    if let Some(entry) = entries.get_mut(id) {
                        entry.handle = Some(handle);
                        entry.status = status.clone();
                    }
                }
                self.emit_status(id, &status);
                self.log(&format!(
                    "隧道已建立：127.0.0.1:{port} -> {}:{}",
                    mapping.target_host, mapping.target_port
                ));
                Ok(port)
            }
            Err(e) => {
                let status = TunnelStatus::Error { message: e.clone() };
                {
                    let mut entries = self.entries.lock().unwrap();
                    if let Some(entry) = entries.get_mut(id) {
                        entry.status = status.clone();
                    }
                }
                self.emit_status(id, &status);
                self.log(&format!("隧道建立失败：{e}"));
                Err(e)
            }
        }
    }

    /// 停止一条隧道。多次调用安全。
    pub fn stop(&self, id: &str) {
        let removed = {
            let mut entries = self.entries.lock().unwrap();
            let entry = entries.get_mut(id);
            match entry {
                Some(e) => {
                    if let Some(handle) = e.handle.take() {
                        handle.cancel.cancel();
                    }
                    e.status = TunnelStatus::Stopped;
                    true
                }
                None => false,
            }
        };
        if removed {
            self.emit_status(id, &TunnelStatus::Stopped);
            self.log(&format!("隧道已停止：{id}"));
        }
    }

    /// 停止所有隧道（退出时调用）。
    pub fn stop_all(&self) {
        let ids: Vec<String> = self.entries.lock().unwrap().keys().cloned().collect();
        for id in ids {
            self.stop(&id);
        }
    }

    /// 移除一条隧道的记录（映射被删除时）。
    pub fn remove(&self, id: &str) {
        self.stop(id);
        self.entries.lock().unwrap().remove(id);
    }
}

fn chrono_now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_millis() as u64)
        .unwrap_or(0)
}
