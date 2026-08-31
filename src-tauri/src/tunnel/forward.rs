//! russh 本地端口转发：连接跳板机 → 密码认证 → 本地监听 →
//! 每个入站连接开一条 direct-tcpip 通道 → 双向拷贝。
//!
//! 等价于 `ssh -N -L <local>:<target_host>:<target_port> <user>@<jumphost>`。

use std::net::SocketAddr;
use std::sync::Arc;
use std::time::Duration;

use russh::client;
use russh::client::Msg;
use russh::keys::key::PublicKey;
use russh::Channel;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::{TcpListener, TcpStream};
use tokio_util::sync::CancellationToken;

use crate::config::Mapping;

/// 跳板机连接参数
#[derive(Debug, Clone)]
pub struct Jumphost {
    pub host: String,
    pub port: u16,
    pub username: String,
    pub password: String,
}

/// 一条运行中的隧道句柄
pub struct ForwardHandle {
    /// 实际绑定的本地端口（自动分配时由系统决定）
    pub actual_local_port: u16,
    /// 取消令牌：cancel 时停止监听与所有转发
    pub cancel: CancellationToken,
}

/// 客户端 Handler：不校验 host key（对齐旧版 paramiko AutoAddPolicy）。
struct NoCheckHandler;

#[async_trait::async_trait]
impl client::Handler for NoCheckHandler {
    type Error = russh::Error;

    async fn check_server_key(
        &mut self,
        _server_public_key: &PublicKey,
    ) -> Result<bool, Self::Error> {
        Ok(true)
    }
}

/// 建立 SSH 连接并完成密码认证。
async fn connect_and_auth(jump: &Jumphost) -> Result<client::Handle<NoCheckHandler>, String> {
    let mut config = client::Config::default();
    // 30s keepalive，防止长连接被踢（对齐旧版 set_keepalive=30）
    config.keepalive_interval = Some(Duration::from_secs(30));
    let config = Arc::new(config);

    let mut handle = client::connect(config, (jump.host.as_str(), jump.port), NoCheckHandler)
        .await
        .map_err(|e| friendly(e, 0))?;

    let ok = handle
        .authenticate_password(&jump.username, &jump.password)
        .await
        .map_err(|e| friendly(e, 0))?;
    if !ok {
        return Err("认证失败：用户名或密码错误".into());
    }
    Ok(handle)
}

/// 启动一条本地转发隧道。
///
/// `mapping.local_port = 0` 表示由操作系统自动分配。
/// 返回实际本地端口。失败返回带中文提示的错误。
pub async fn start_forward(
    jump: &Jumphost,
    mapping: &Mapping,
) -> Result<ForwardHandle, String> {
    let handle = connect_and_auth(jump).await?;

    // ---------- 本地监听 ----------
    let bind: SocketAddr = format!("127.0.0.1:{}", mapping.local_port).parse().unwrap();
    let listener = TcpListener::bind(bind)
        .await
        .map_err(|e| friendly(e, mapping.local_port))?;
    let actual_port = listener
        .local_addr()
        .map(|a| a.port())
        .unwrap_or(mapping.local_port);

    let cancel = CancellationToken::new();

    // ---------- 接受循环 ----------
    let accept_cancel = cancel.clone();
    let target_host = mapping.target_host.clone();
    let target_port = mapping.target_port;
    tokio::spawn(async move {
        loop {
            tokio::select! {
                _ = accept_cancel.cancelled() => break,
                res = listener.accept() => {
                    match res {
                        Ok((stream, _)) => {
                            // 目标地址由跳板机连接，originator 填本地回环
                            let ch = handle
                                .channel_open_direct_tcpip(
                                    &target_host,
                                    target_port as u32,
                                    "127.0.0.1",
                                    actual_port as u32,
                                )
                                .await;
                            match ch {
                                Ok(channel) => spawn_forward_pair(channel, stream),
                                Err(e) => log::warn!("打开 direct-tcpip 通道失败：{}", e),
                            }
                        }
                        Err(e) => {
                            log::warn!("本地监听 accept 失败：{}", e);
                            break;
                        }
                    }
                }
            }
        }
    });

    Ok(ForwardHandle {
        actual_local_port: actual_port,
        cancel,
    })
}

/// 双向拷贝：本地 TCP 流 <-> SSH 通道。任一侧结束则关闭另一侧。
fn spawn_forward_pair(channel: Channel<Msg>, stream: TcpStream) {
    tokio::spawn(async move {
        let mut channel = channel;
        // writer 只克隆内部 sender，可提前创建，与 reader 的长借用不冲突
        let mut writer = channel.make_writer();

        let (mut tcp_reader, mut tcp_writer) = stream.into_split();

        // 本地 -> 远端
        let to_remote = async {
            let mut buf = [0u8; 16 * 1024];
            loop {
                let n = match tcp_reader.read(&mut buf).await {
                    Ok(0) | Err(_) => break,
                    Ok(n) => n,
                };
                if writer.write_all(&buf[..n]).await.is_err() {
                    break;
                }
            }
        };
        // 远端 -> 本地（reader 的借用限制在块内，结束后释放对 channel 的可变借用）
        let to_local = async {
            let mut reader = channel.make_reader();
            let mut buf = [0u8; 16 * 1024];
            loop {
                let n = match reader.read(&mut buf).await {
                    Ok(0) | Err(_) => break,
                    Ok(n) => n,
                };
                if tcp_writer.write_all(&buf[..n]).await.is_err() {
                    break;
                }
            }
            let _ = tcp_writer.shutdown().await;
        };

        tokio::join!(to_remote, to_local);
        // 两侧都结束后再通知远端 EOF 并关闭通道
        let _ = channel.eof().await;
        let _ = channel.close().await;
    });
}

/// 仅测试连接（认证成功即返回），不建立转发。
pub async fn test_only(jump: &Jumphost) -> Result<(), String> {
    connect_and_auth(jump).await?;
    Ok(())
}

/// 把 russh / IO 异常翻译成中文友好提示（对齐旧版 _friendly_error）。
fn friendly(e: impl std::fmt::Display, local_port: u16) -> String {
    let msg = e.to_string().to_lowercase();
    if msg.contains("auth") || msg.contains("password") {
        "认证失败：用户名或密码错误".into()
    } else if msg.contains("refused") || msg.contains("timed out") || msg.contains("timeout") {
        "无法连接跳板机：连接被拒绝或超时，请检查主机和端口".into()
    } else if msg.contains("name or service not known")
        || msg.contains("getaddrinfo")
        || msg.contains("no address")
        || msg.contains("resolve")
    {
        "无法解析跳板机地址：主机名不存在".into()
    } else if msg.contains("address already in use") {
        let port_info = if local_port != 0 {
            format!("（本地端口 {local_port}）")
        } else {
            String::new()
        };
        format!("本地端口被占用{port_info}：请改用「自动端口」或换一个端口")
    } else {
        e.to_string()
    }
}
