use jumptunnel_lib::{config::Config, tunnel::forward::Jumphost};

#[tokio::main]
async fn main() {
    let jump = Jumphost {
        host: "10.2.68.128".into(),
        port: 51730,
        username: "simsadmin".into(),
        password: "sims@Admin#xyz".into(),
    };
    let mapping = jumptunnel_lib::config::Mapping {
        id: "test".into(),
        auto_port: true,
        local_port: 0,
        target_host: "172.17.12.22".into(),
        target_port: 443,
        scheme: "https".into(),
        note: String::new(),
    };
    match jumptunnel_lib::tunnel::forward::start_forward(&jump, &mapping).await {
        Ok(h) => {
            println!("TUNNEL_OK port={}", h.actual_local_port);
            // 保持 3 秒让转发循环运行
            tokio::time::sleep(std::time::Duration::from_secs(3)).await;
            h.cancel.cancel();
            println!("TUNNEL_STOPPED");
        }
        Err(e) => {
            println!("TUNNEL_ERR: {}", e);
            std::process::exit(1);
        }
    }
}
