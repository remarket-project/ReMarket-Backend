"""
Quản lý kết nối WebSocket cho thông báo real-time.

Quản lý các kết nối WebSocket cho gửi thông báo real-time đến người dùng.
Hỗ trợ nhiều kết nối cho mỗi người dùng (nhiều tab browser/thiết bị).
"""

import asyncio
import uuid
import logging
from typing import Dict, Set
from dataclasses import dataclass, field
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Trả về datetime UTC không có timezone cho khả năng tương thích cơ sở dữ liệu.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class ConnectionInfo:
    """Thông tin về kết nối WebSocket."""
    websocket: WebSocket
    user_id: uuid.UUID
    connected_at: datetime = field(default_factory=utc_now)
    last_ping: datetime = field(default_factory=utc_now)


class WebSocketManager:
    """
    Quản lý kết nối WebSocket cho thông báo real-time.

    Tính năng:
    - Nhiều kết nối cho mỗi người dùng (nhiều tab/thiết bị)
    - Hoạt động an toàn với asyncio.Lock
    - Dọn dẹp tự động khi ngắt kết nối
    - Theo dõi trạng thái online của người dùng
    """

    def __init__(self):
        self._user_connections: Dict[uuid.UUID, Set[str]] = {}
        self._connections: Dict[str, ConnectionInfo] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: uuid.UUID) -> str:
        """
        Chấp nhận kết nối WebSocket và đăng ký người dùng.

        Args:
            websocket: Kết nối WebSocket
            user_id: UUID của người dùng được xác thực

        Returns:
            connection_id: ID duy nhất cho kết nối này
        """
        await websocket.accept()
        connection_id = str(uuid.uuid4())

        async with self._lock:
            conn_info = ConnectionInfo(websocket=websocket, user_id=user_id)
            self._connections[connection_id] = conn_info

            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)

        logger.info(f"WebSocket kết nối: user={user_id}, conn={connection_id}")
        return connection_id

    async def disconnect(self, connection_id: str):
        """
        Xóa kết nối khi ngắt.

        Args:
            connection_id: ID kết nối cần xóa
        """
        async with self._lock:
            if connection_id not in self._connections:
                return

            conn_info = self._connections.pop(connection_id)
            user_id = conn_info.user_id

            if user_id in self._user_connections:
                self._user_connections[user_id].discard(connection_id)
                if not self._user_connections[user_id]:
                    del self._user_connections[user_id]

        logger.info(f"WebSocket ngắt: conn={connection_id}")

    async def send_to_user(self, user_id: uuid.UUID, message: dict):
        """
        Gửi tin nhắn đến tất cả kết nối của một người dùng.

        Args:
            user_id: UUID của người dùng nhận
            message: Dict tin nhắn (sẽ được chuyển thành JSON)
        """
        async with self._lock:
            connection_ids = self._user_connections.get(user_id, set()).copy()

        disconnected = []
        for conn_id in connection_ids:
            conn_info = self._connections.get(conn_id)
            if conn_info:
                try:
                    await conn_info.websocket.send_json(message)
                except Exception as e:
                    logger.warning(f"Lỗi gửi đến {conn_id}: {e}")
                    disconnected.append(conn_id)

        for conn_id in disconnected:
            await self.disconnect(conn_id)

    async def broadcast_to_users(self, user_ids: list[uuid.UUID], message: dict):
        """
        Gửi tin nhắn đến nhiều người dùng.

        Args:
            user_ids: Danh sách UUID người dùng
            message: Dict tin nhắn
        """
        tasks = [self.send_to_user(uid, message) for uid in user_ids]
        await asyncio.gather(*tasks, return_exceptions=True)

    def get_online_users(self) -> Set[uuid.UUID]:
        """
        Lấy tập hợp UUID người dùng hiện đang kết nối.

        Returns:
            Tập hợp UUID có ít nhất một kết nối hoạt động
        """
        return set(self._user_connections.keys())

    def is_user_online(self, user_id: uuid.UUID) -> bool:
        """
        Kiểm tra người dùng có kết nối hoạt động không.

        Args:
            user_id: UUID người dùng

        Returns:
            True nếu người dùng có ít nhất một kết nối WebSocket hoạt động
        """
        return user_id in self._user_connections

    async def update_last_ping(self, connection_id: str):
        """
        Cập nhật timestamp ping cuối cùng cho kết nối.

        Args:
            connection_id: ID kết nối cần cập nhật
        """
        conn_info = self._connections.get(connection_id)
        if conn_info:
            conn_info.last_ping = utc_now()


# Global singleton instance
ws_manager = WebSocketManager()
