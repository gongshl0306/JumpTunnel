//! 配置持久化：跳板机档案 + 映射列表。
//!
//! 新配置位于 Tauri app_config_dir（Windows: %APPDATA%\com.jumptunnel.app\config.json），
//! schema 与旧版 Python 完全一致，首次启动自动从 ~/.ssh_forward_tool/config.json 导入。

use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};

/// 跳板机档案
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Profile {
    pub name: String,
    pub host: String,
    #[serde(default = "default_port")]
    pub port: u16,
    pub username: String,
    #[serde(default)]
    pub password: String,
}

fn default_port() -> u16 {
    22
}

/// 一条端口映射
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct Mapping {
    /// 后端分配的稳定 id（旧配置无此字段时由导入逻辑补齐）
    #[serde(default)]
    pub id: String,
    pub auto_port: bool,
    #[serde(default)]
    pub local_port: u16,
    pub target_host: String,
    pub target_port: u16,
    #[serde(default = "default_scheme")]
    pub scheme: String,
    #[serde(default)]
    pub note: String,
}

fn default_scheme() -> String {
    "http".into()
}

/// 完整配置（与旧版 JSON 结构一致）
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
pub struct Config {
    #[serde(default)]
    pub profiles: Vec<Profile>,
    #[serde(default)]
    pub last_mappings: Vec<Mapping>,
    #[serde(default)]
    pub last_profile: String,
}

/// 配置存储：文件读写 + 内存缓存（Mutex 保护）。
pub struct ConfigStore {
    path: PathBuf,
    data: Mutex<Config>,
}

impl ConfigStore {
    /// 加载配置：优先新路径；不存在则尝试从旧版路径导入。
    pub fn load() -> Self {
        let path = Self::config_path();
        let mut data = Self::read_file(&path);
        if data == Config::default() {
            if let Some(legacy) = Self::read_legacy() {
                log::info!("已从旧版配置导入：{}", Self::legacy_path().display());
                data = legacy;
                Self::write_file(&path, &data);
            }
        }
        Self {
            path,
            data: Mutex::new(data),
        }
    }

    fn config_path() -> PathBuf {
        // 与 tauri.conf.json 的 identifier 保持一致
        let base = dirs::config_dir().unwrap_or_else(|| PathBuf::from("."));
        base.join("com.jumptunnel.app").join("config.json")
    }

    fn legacy_path() -> PathBuf {
        let home = dirs::home_dir().unwrap_or_else(|| PathBuf::from("."));
        home.join(".ssh_forward_tool").join("config.json")
    }

    fn read_file(path: &PathBuf) -> Config {
        match std::fs::read_to_string(path) {
            Ok(s) => serde_json::from_str(&s).unwrap_or_default(),
            Err(_) => Config::default(),
        }
    }

    fn read_legacy() -> Option<Config> {
        let p = Self::legacy_path();
        if !p.exists() {
            return None;
        }
        let s = std::fs::read_to_string(p).ok()?;
        let mut cfg: Config = serde_json::from_str(&s).ok()?;
        // 旧配置无 id 字段，补齐
        for m in &mut cfg.last_mappings {
            if m.id.is_empty() {
                m.id = new_id();
            }
        }
        Some(cfg)
    }

    fn write_file(path: &PathBuf, data: &Config) {
        if let Some(parent) = path.parent() {
            let _ = std::fs::create_dir_all(parent);
        }
        if let Ok(s) = serde_json::to_string_pretty(data) {
            let _ = std::fs::write(path, s);
        }
    }

    // ---------- 读取 ----------

    pub fn snapshot(&self) -> Config {
        self.data.lock().unwrap().clone()
    }

    // ---------- 档案 CRUD ----------

    pub fn upsert_profile(&self, profile: Profile) {
        let mut data = self.data.lock().unwrap();
        if let Some(p) = data.profiles.iter_mut().find(|p| p.name == profile.name) {
            *p = profile;
        } else {
            data.profiles.push(profile);
        }
        drop(data);
        self.persist();
    }

    pub fn delete_profile(&self, name: &str) {
        let mut data = self.data.lock().unwrap();
        data.profiles.retain(|p| p.name != name);
        if data.last_profile == name {
            data.last_profile.clear();
        }
        drop(data);
        self.persist();
    }

    pub fn set_last_profile(&self, name: &str) {
        let mut data = self.data.lock().unwrap();
        data.last_profile = name.to_string();
        drop(data);
        self.persist();
    }

    // ---------- 映射 ----------

    pub fn set_last_mappings(&self, mappings: Vec<Mapping>) {
        let mut data = self.data.lock().unwrap();
        data.last_mappings = mappings;
        drop(data);
        self.persist();
    }

    fn persist(&self) {
        let data = self.data.lock().unwrap().clone();
        Self::write_file(&self.path, &data);
    }
}

/// 生成短 id（时间戳 + 随机后缀）
pub fn new_id() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    format!("{:x}-{:04x}", ts, (ts % 0xffff) as u16 ^ 0x5a5a)
}
