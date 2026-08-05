"""单条 SSH 端口转发隧道的封装。

等价于：ssh -N -L <local_port>:<target_host>:<target_port> <user>@<jumphost>
用 sshtunnel 在代码内完成密码登录与端口映射，每个映射独立一条隧道，
可单独启停。local_port=0 表示让操作系统自动分配空闲端口。
"""

import socket
from typing import Optional, Tuple

try:
    from sshtunnel import SSHTunnelForwarder, BaseSSHTunnelForwarderError
    from paramiko.ssh_exception import SSHException
except ImportError:  # 依赖未安装时的友好降级
    SSHTunnelForwarder = None  # type: ignore
    SSHException = Exception  # type: ignore
    BaseSSHTunnelForwarderError = Exception  # type: ignore


class TunnelError(Exception):
    """隧道启停过程中发生的错误。"""


def _friendly_error(e: Exception, local_port: int = 0) -> str:
    """把底层 sshtunnel/paramiko 异常翻译成中文友好提示。"""
    msg = str(e).lower()
    if "auth" in msg or "password" in msg:
        return "认证失败：用户名或密码错误"
    if "refused" in msg or "timed out" in msg or "timeout" in msg:
        return "无法连接跳板机：连接被拒绝或超时，请检查主机和端口"
    if "name or service not known" in msg or "getaddrinfo" in msg or "no address" in msg:
        return "无法解析跳板机地址：主机名不存在"
    if "address already in use" in msg or ("98" in msg and "bind" in str(e).lower()):
        port_info = f"（本地端口 {local_port}）" if local_port else ""
        return f"本地端口被占用{port_info}：请改用「自动端口」或换一个端口"
    if "remote" in msg and ("refused" in msg or "connect" in msg):
        return "跳板机无法连到目标地址：请确认目标 IP 和端口在跳板机上可达"
    return str(e)


class MappingTunnel:
    """一条本地端口 -> 目标 host:port 的转发隧道。"""

    def __init__(
        self,
        jumphost: str,
        jumpport: int,
        username: str,
        password: str,
        target_host: str,
        target_port: int,
        local_port: int = 0,
    ):
        if SSHTunnelForwarder is None:
            raise TunnelError(
                "未安装 sshtunnel，请先运行：pip install -r requirements.txt"
            )
        self.jumphost = jumphost
        self.jumpport = jumpport
        self.username = username
        self.password = password
        self.target_host = target_host
        self.target_port = target_port
        self.local_port = local_port  # 0 表示自动分配

        self._tunnel: Optional[SSHTunnelForwarder] = None
        self.actual_local_port: Optional[int] = None  # 启动后填入实际端口
        self.errored: bool = False  # 正式状态字段，替代 monkey-patch 的 _errored

    # ---------- 生命周期 ----------

    def start(self) -> int:
        """启动隧道，返回实际绑定的本地端口。失败抛 TunnelError（含友好提示）。"""
        if self._tunnel is not None and self._tunnel.is_active:
            # 已经在运行，直接返回当前端口
            return self.actual_local_port or 0

        self.errored = False
        try:
            self._tunnel = SSHTunnelForwarder(
                (self.jumphost, int(self.jumpport)),
                ssh_username=self.username,
                ssh_password=self.password,
                remote_bind_address=(self.target_host, int(self.target_port)),
                local_bind_address=("127.0.0.1", int(self.local_port)),
                set_keepalive=30,  # 30s 发 keepalive，防止长连接被踢
            )
            self._tunnel.start()
        except TunnelError:
            raise
        except (SSHException, BaseSSHTunnelForwarderError, socket.error, ValueError) as e:
            self._tunnel = None
            self.errored = True
            raise TunnelError(_friendly_error(e, self.local_port)) from e

        # local_bind_ports 是 sshtunnel 维护的实际端口列表
        ports = getattr(self._tunnel, "local_bind_ports", [])
        self.actual_local_port = ports[0] if ports else self.local_port
        return self.actual_local_port

    def stop(self) -> None:
        """停止隧道。多次调用安全。"""
        if self._tunnel is not None:
            try:
                self._tunnel.stop()
            except Exception:
                pass
            self._tunnel = None
        self.actual_local_port = None

    def is_active(self) -> bool:
        """隧道是否处于运行状态。"""
        return self._tunnel is not None and self._tunnel.is_active

    def info(self) -> str:
        """可读的隧道信息，用于日志。"""
        lp = self.actual_local_port if self.actual_local_port else self.local_port
        return f"127.0.0.1:{lp} -> {self.target_host}:{self.target_port}"
