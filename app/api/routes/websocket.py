"""
WebSocket endpoint cho thông báo real-time.

Kết nối tới: ws://host/api/v1/ws?token=<jwt_access_token>

Định dạng tin nhắn từ server:
{
    "type": "notification",  // hoặc "connected", "pong"
    "data": {...}
}

Client có thể gửi:
{
    "type": "ping"
}
"""

import uuid
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, status
from app.core.websocket_manager import ws_manager
from app.core.security import decode_access_token

logger = logging.getLogger(__name__)
router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token cho xác thực")
):
    """
    WebSocket endpoint cho thông báo real-time.

    URL kết nối: ws://host/api/v1/ws?token=<jwt_access_token>

    Tin nhắn từ server:
    - {"type": "connected", "connection_id": "...", "user_id": "..."}
    - {"type": "notification", "data": {...}}
    - {"type": "pong"}

    Tin nhắn từ client:
    - {"type": "ping"} -> Server trả {"type": "pong"}
    """
    try:
        payload = decode_access_token(token)
        user_id = uuid.UUID(payload.get("sub"))
    except Exception as e:
        logger.warning(f"WebSocket auth failed: {e}")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Token không hợp lệ")
        return

    connection_id = await ws_manager.connect(websocket, user_id)

    try:
        await websocket.send_json({
            "type": "connected",
            "connection_id": connection_id,
            "user_id": str(user_id)
        })

        while True:
            try:
                data = await websocket.receive_json()

                if data.get("type") == "ping":
                    await ws_manager.update_last_ping(connection_id)
                    await websocket.send_json({"type": "pong"})

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(
                    f"WebSocket error cho kết nối {connection_id}: {e}")
                break

    finally:
        await ws_manager.disconnect(connection_id)
