//! 后端 → 前端的事件定义。

use serde::Serialize;

use crate::tunnel::TunnelStatus;

/// 隧道状态变化事件
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TunnelStatusEvent {
    pub id: String,
    pub status: TunnelStatus,
}

/// 日志事件
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct LogEvent {
    pub ts: u64,
    pub level: String,
    pub msg: String,
}
