// 启动隧道并保持运行，供外部验证转发
use jumptunnel_lib::config::Mapping;
use jumptunnel_lib::tunnel::forward::{Jumphost, start_forward};

#[tokio::main]
async fn main() {
    env_logger::init();
    // 用 TBJ 跳板机，目标用跳板机自身（保证可达）
    let jump = Jumphost {
        host: "10.2.208.244".into(),
        port: 22,
        username: "caozhf".into(),
        password: "tjbmc666".into(),
    };
    let mapping = Mapping {
        id: "test".into(),
        auto_port: true,
        local_port: 0,
        target_host: "10.2.208.244".into(),
        target_port: 22,
        scheme: "tcp".into(),
        note: String::new(),
    };
    match start_forward(&jump, &mapping).await {
        Ok(h) => {
            println!("PORT={}", h.actual_local_port);
            tokio::time::sleep(std::time::Duration::from_secs(30)).await;
            h.cancel.cancel();
        }
        Err(e) => {
            eprintln!("ERR: {}", e);
            std::process::exit(1);
        }
    }
}
