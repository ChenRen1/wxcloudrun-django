"""企业微信客服通信模块。"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import time
from collections import deque
from typing import Any
from uuid import uuid4
from xml.etree import ElementTree

import httpx
from Crypto.Cipher import AES

from app.src.wecom.config import WeComKFSettings, load_wecom_settings


DEFAULT_CALLBACK_CACHE_SIZE = 20


class WeComKFError(RuntimeError):
    """企业微信客服调用失败。"""


class WeComAccessTokenCache:
    """最小 access_token 缓存。"""

    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0

    def get(self) -> str | None:
        if self._token and time.time() < self._expires_at:
            return self._token
        return None

    def set(self, token: str, expires_in: int) -> None:
        self._token = token
        self._expires_at = time.time() + max(expires_in - 120, 60)


class WeComKFClient:
    """微信客服 API 客户端。"""

    def __init__(self, settings: WeComKFSettings) -> None:
        self.settings = settings
        self._token_cache = WeComAccessTokenCache()

    async def get_access_token(self, refresh: bool = False) -> str:
        """获取 access_token。"""

        if not refresh:
            cached = self._token_cache.get()
            if cached:
                return cached

        if not self.settings.corp_id or not self.settings.corp_secret:
            raise WeComKFError("缺少 WECOM_CORP_ID 或 WECOM_KF_SECRET")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.settings.base_url}/cgi-bin/gettoken",
                params={
                    "corpid": self.settings.corp_id,
                    "corpsecret": self.settings.corp_secret,
                },
            )
        response.raise_for_status()
        data = response.json()
        _raise_for_errcode(data)

        access_token = data["access_token"]
        self._token_cache.set(access_token, int(data.get("expires_in", 7200)))
        return access_token

    async def create_account(self, name: str, media_id: str) -> dict[str, Any]:
        """创建客服帐号。"""

        payload = {"name": name, "media_id": media_id}
        return await self._post("/cgi-bin/kf/account/add", payload)

    async def sync_messages(
        self,
        *,
        token: str,
        open_kfid: str,
        cursor: str | None = None,
        limit: int = 100,
        voice_format: int = 0,
    ) -> dict[str, Any]:
        """读取消息。"""

        payload: dict[str, Any] = {
            "token": token,
            "open_kfid": open_kfid,
            "limit": limit,
            "voice_format": voice_format,
        }
        if cursor:
            payload["cursor"] = cursor
        return await self._post("/cgi-bin/kf/sync_msg", payload)

    async def send_text_message(
        self,
        *,
        touser: str,
        open_kfid: str,
        content: str,
        msgid: str | None = None,
    ) -> dict[str, Any]:
        """发送文本消息。"""

        payload = {
            "touser": touser,
            "open_kfid": open_kfid,
            "msgtype": "text",
            "text": {"content": content},
            "msgid": msgid or uuid4().hex,
        }
        return await self._post("/cgi-bin/kf/send_msg", payload)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        access_token = await self.get_access_token()
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.settings.base_url}{path}",
                params={"access_token": access_token},
                json=payload,
            )
        response.raise_for_status()
        data = response.json()
        _raise_for_errcode(data)
        return data


class WeComCallbackCrypto:
    """企业微信回调最小解密器。"""

    block_size = 32

    def __init__(self, token: str, encoding_aes_key: str, receive_id: str) -> None:
        if len(encoding_aes_key) != 43:
            raise WeComKFError("WECOM_CALLBACK_AES_KEY 长度应为 43")
        self.token = token
        self.receive_id = receive_id
        self.key = base64.b64decode(f"{encoding_aes_key}=")
        self.iv = self.key[:16]

    def verify_url(self, *, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> str:
        self._verify_signature(msg_signature, timestamp, nonce, echostr)
        return self._decrypt(encrypted=echostr, receive_id=self.receive_id)

    def decrypt_callback_body(
        self,
        *,
        msg_signature: str,
        timestamp: str,
        nonce: str,
        xml_body: bytes,
    ) -> dict[str, Any]:
        root = ElementTree.fromstring(xml_body)
        encrypt = _find_required_text(root, "Encrypt")
        self._verify_signature(msg_signature, timestamp, nonce, encrypt)
        xml_text = self._decrypt(encrypted=encrypt, receive_id=self.receive_id)
        message_root = ElementTree.fromstring(xml_text.encode("utf-8"))
        return _xml_to_dict(message_root)

    def _verify_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypted: str) -> None:
        raw = "".join(sorted([self.token, timestamp, nonce, encrypted]))
        expected = hashlib.sha1(raw.encode("utf-8")).hexdigest()
        if expected != msg_signature:
            raise WeComKFError("企业微信回调签名校验失败")

    def _decrypt(self, *, encrypted: str, receive_id: str) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        decoded = base64.b64decode(encrypted)
        plain_padded = cipher.decrypt(decoded)
        plain = _pkcs7_unpad(plain_padded)

        xml_length = struct.unpack(">I", plain[16:20])[0]
        xml_content = plain[20 : 20 + xml_length]
        from_receive_id = plain[20 + xml_length :].decode("utf-8")
        if from_receive_id != receive_id:
            raise WeComKFError("企业微信回调 receive_id 校验失败")
        return xml_content.decode("utf-8")


class CallbackStore:
    """内存中的最小回调存储。"""

    def __init__(self, max_items: int = DEFAULT_CALLBACK_CACHE_SIZE) -> None:
        self._items: deque[dict[str, Any]] = deque(maxlen=max_items)

    def append(self, item: dict[str, Any]) -> None:
        self._items.appendleft(item)

    def list(self) -> list[dict[str, Any]]:
        return list(self._items)

    def latest_sync_token(self) -> tuple[str, str] | None:
        for item in self._items:
            if item.get("Event") == "kf_msg_or_event" and item.get("Token") and item.get("OpenKfId"):
                return item["Token"], item["OpenKfId"]
        return None


class ProcessedMessageStore:
    """已处理消息去重缓存。"""

    def __init__(self, max_items: int = 200) -> None:
        self._items: deque[str] = deque(maxlen=max_items)
        self._index: set[str] = set()

    def has(self, msgid: str) -> bool:
        return msgid in self._index

    def add(self, msgid: str) -> None:
        if msgid in self._index:
            return
        if len(self._items) == self._items.maxlen:
            removed = self._items.pop()
            self._index.discard(removed)
        self._items.appendleft(msgid)
        self._index.add(msgid)


def create_wecom_client_from_env() -> WeComKFClient:
    return WeComKFClient(load_wecom_settings())


def create_callback_crypto_from_env() -> WeComCallbackCrypto:
    settings = load_wecom_settings()
    if not settings.callback_token or not settings.encoding_aes_key or not settings.receive_id:
        raise WeComKFError("缺少 WECOM_CALLBACK_TOKEN / WECOM_CALLBACK_AES_KEY / WECOM_CALLBACK_RECEIVE_ID")
    return WeComCallbackCrypto(
        token=settings.callback_token,
        encoding_aes_key=settings.encoding_aes_key,
        receive_id=settings.receive_id,
    )


def _raise_for_errcode(data: dict[str, Any]) -> None:
    if int(data.get("errcode", 0)) != 0:
        raise WeComKFError(json.dumps(data, ensure_ascii=False))


def _pkcs7_unpad(data: bytes) -> bytes:
    pad = data[-1]
    if pad < 1 or pad > WeComCallbackCrypto.block_size:
        raise WeComKFError("企业微信回调解密后 padding 非法")
    return data[:-pad]


def _find_required_text(root: ElementTree.Element, tag: str) -> str:
    node = root.find(tag)
    if node is None or node.text is None:
        raise WeComKFError(f"回调 XML 缺少字段 {tag}")
    return node.text


def _xml_to_dict(root: ElementTree.Element) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for child in root:
        data[child.tag] = child.text or ""
    return data
