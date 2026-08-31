//! JumpTunnel — SSH 端口转发工具（Rust + Tauri 版）
//!
//! 架构：Rust 后端是唯一事实源。每条映射对应一个 tokio 任务，
//! 内部维护状态机（Stopped → Connecting → Running → Error），
//! 状态变化与日志通过 Tauri 事件推给前端，前端纯渲染。

mod commands;
pub mod config;
mod events;
pub mod tunnel;

use std::sync::Arc;

use tauri::Manager;

pub use config::ConfigStore;
pub use tunnel::TunnelManager;

/// 应用共享状态：配置存储 + 隧道管理器。
pub struct AppState {
    pub config: Arc<ConfigStore>,
    pub tunnels: Arc<TunnelManager>,
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    env_logger::init();

    let config = Arc::new(ConfigStore::load());
    let tunnels = Arc::new(TunnelManager::new());

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            // 已有实例在运行：把主窗口带到前台
            if let Some(win) = app.get_webview_window("main") {
                let _ = win.show();
                let _ = win.set_focus();
            }
        }))
        .manage(AppState { config, tunnels })
        .invoke_handler(tauri::generate_handler![
            commands::get_initial_state,
            commands::list_profiles,
            commands::save_profile,
            commands::delete_profile,
            commands::set_last_profile,
            commands::add_mapping,
            commands::update_mapping,
            commands::remove_mapping,
            commands::test_connection,
            commands::start_tunnel,
            commands::stop_tunnel,
            commands::start_all,
            commands::stop_all,
        ])
        .setup(|app| {
            // 注入 AppHandle 供隧道管理器 emit 事件
            let state = app.state::<AppState>();
            state.tunnels.set_app(app.handle().clone());
            Ok(())
        })
        .on_window_event(|window, event| {
            // 主窗口关闭时停止所有隧道（对齐旧版退出清理）
            if window.label() == "main" {
                if let tauri::WindowEvent::CloseRequested { .. } = event {
                    let app = window.app_handle();
                    let state = app.state::<AppState>();
                    state.tunnels.stop_all();
                }
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
