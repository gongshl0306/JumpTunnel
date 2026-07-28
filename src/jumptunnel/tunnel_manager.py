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

    # ---------- 生命周期 ----------

    def start(self) -> int:
        """启动隧道，返回实际绑定的本地端口。失败抛 TunnelError。"""
        if self._tunnel is not None and self._tunnel.is_active:
            # 已经在运行，直接返回当前端口
            return self.actual_local_port or 0

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
        except (SSHException, BaseSSHTunnelForwarderError, socket.error, ValueError) as e:
            self._tunnel = None
            raise TunnelError(str(e)) from e

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
