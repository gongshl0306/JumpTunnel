//! Tauri IPC 命令：前端 invoke 的入口。

use serde::Serialize;
use tauri::State;

use crate::config::{Config, Mapping, Profile, new_id};
use crate::tunnel::forward::Jumphost;
use crate::AppState;

/// 启动时给前端的全量快照
#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InitialState {
    pub config: Config,
    pub tunnel_statuses: Vec<TunnelStatusPair>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TunnelStatusPair {
    pub id: String,
    pub status: crate::tunnel::TunnelStatus,
}

// ---------- 配置 ----------

#[tauri::command]
pub fn get_initial_state(state: State<'_, AppState>) -> InitialState {
    let config = state.config.snapshot();
    let tunnel_statuses = state
        .tunnels
        .status_snapshot()
        .into_iter()
        .map(|(id, status)| TunnelStatusPair { id, status })
        .collect();
    InitialState {
        config,
        tunnel_statuses,
    }
}

#[tauri::command]
pub fn list_profiles(state: State<'_, AppState>) -> Vec<Profile> {
    state.config.snapshot().profiles
}

#[tauri::command]
pub fn save_profile(state: State<'_, AppState>, profile: Profile) {
    state.config.upsert_profile(profile);
}

#[tauri::command]
pub fn delete_profile(state: State<'_, AppState>, name: String) {
    state.config.delete_profile(&name);
}

#[tauri::command]
pub fn set_last_profile(state: State<'_, AppState>, name: String) {
    state.config.set_last_profile(&name);
}

// ---------- 映射 ----------

#[tauri::command]
pub fn add_mapping(state: State<'_, AppState>, mapping: Mapping) -> Mapping {
    let mut mapping = mapping;
    if mapping.id.is_empty() {
        mapping.id = new_id();
    }
    let mut cfg = state.config.snapshot();
    cfg.last_mappings.push(mapping.clone());
    state.config.set_last_mappings(cfg.last_mappings);
    mapping
}

#[tauri::command]
pub fn update_mapping(state: State<'_, AppState>, mapping: Mapping) {
    let mut cfg = state.config.snapshot();
    if let Some(m) = cfg.last_mappings.iter_mut().find(|m| m.id == mapping.id) {
        *m = mapping;
    }
    state.config.set_last_mappings(cfg.last_mappings);
}

#[tauri::command]
pub fn remove_mapping(state: State<'_, AppState>, id: String) {
    state.tunnels.remove(&id);
    let mut cfg = state.config.snapshot();
    cfg.last_mappings.retain(|m| m.id != id);
    state.config.set_last_mappings(cfg.last_mappings);
}

// ---------- 隧道 ----------

/// 从前端传入的跳板机参数（输入框当前值）
#[derive(Debug, serde::Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct JumphostInput {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
}

impl From<JumphostInput> for Jumphost {
    fn from(v: JumphostInput) -> Self {
        Self {
            host: v.host,
            port: v.port,
            username: v.username,
            password: v.password,
        }
    }
}

#[tauri::command]
pub async fn test_connection(jump: JumphostInput) -> Result<(), String> {
    let jump = Jumphost::from(jump);
    let result = tokio::time::timeout(
        std::time::Duration::from_secs(8),
        crate::tunnel::forward::test_only(&jump),
    )
    .await;
    match result {
        Ok(Ok(())) => Ok(()),
        Ok(Err(e)) => Err(e),
        Err(_) => Err("无法连接跳板机：连接被拒绝或超时，请检查主机和端口".into()),
    }
}

#[tauri::command]
pub async fn start_tunnel(
    state: State<'_, AppState>,
    id: String,
    jump: JumphostInput,
) -> Result<u16, String> {
    let jump = Jumphost::from(jump);
    let mapping = state
        .config
        .snapshot()
        .last_mappings
        .iter()
        .find(|m| m.id == id)
        .cloned()
        .ok_or_else(|| "映射不存在".to_string())?;
    state.tunnels.start(&id, &jump, &mapping).await
}

#[tauri::command]
pub fn stop_tunnel(state: State<'_, AppState>, id: String) {
    state.tunnels.stop(&id);
}

#[tauri::command]
pub async fn start_all(
    state: State<'_, AppState>,
    jump: JumphostInput,
) -> Result<Vec<(String, Result<u16, String>)>, String> {
    let jump = Jumphost::from(jump);
    let mappings = state.config.snapshot().last_mappings;
    let mut results = Vec::new();
    for m in mappings {
        let r = state.tunnels.start(&m.id, &jump, &m).await;
        results.push((m.id, r));
    }
    Ok(results)
}

#[tauri::command]
pub fn stop_all(state: State<'_, AppState>) {
    state.tunnels.stop_all();
}
