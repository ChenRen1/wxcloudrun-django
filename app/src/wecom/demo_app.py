"""企业微信客服最小测试服务。"""

from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from app.src.agent.service import answer_customer
from app.src.wecom.config import load_wecom_settings
from app.src.wecom.client import (
    CallbackStore,
    ProcessedMessageStore,
    WeComKFError,
    create_callback_crypto_from_env,
    create_wecom_client_from_env,
)


app = FastAPI(title="WeCom KF Demo")
callback_store = CallbackStore()
processed_message_store = ProcessedMessageStore()


class CreateKfAccountRequest(BaseModel):
    """创建客服帐号请求体。"""

    name: str = Field(min_length=1, max_length=16)
    media_id: str = Field(min_length=1)


class SyncMessagesRequest(BaseModel):
    """手动拉取微信客服消息请求体。"""

    token: str = Field(min_length=1)
    open_kfid: str = Field(min_length=1)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)
    voice_format: int = Field(default=0, ge=0, le=1)


class SendTextMessageRequest(BaseModel):
    """发送文本消息请求体。"""

    touser: str = Field(min_length=1)
    open_kfid: str = Field(min_length=1)
    content: str = Field(min_length=1, max_length=2048)
    msgid: str | None = None


class AutoReplyRequest(BaseModel):
    """手动触发自动回复请求体。"""

    token: str = Field(min_length=1)
    open_kfid: str = Field(min_length=1)
    cursor: str | None = None
    limit: int = Field(default=100, ge=1, le=1000)


@app.get("/health")
async def health() -> dict[str, str]:
    """最小健康检查。"""

    return {"status": "ok"}


@app.post("/wecom/kf/accounts")
async def create_kf_account(request: CreateKfAccountRequest) -> dict:
    client = create_wecom_client_from_env()
    try:
        return await client.create_account(name=request.name, media_id=request.media_id)
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/messages/sync")
async def sync_messages(request: SyncMessagesRequest) -> dict:
    client = create_wecom_client_from_env()
    try:
        return await client.sync_messages(
            token=request.token,
            open_kfid=request.open_kfid,
            cursor=request.cursor,
            limit=request.limit,
            voice_format=request.voice_format,
        )
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/messages/sync-latest")
async def sync_latest_messages(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    latest = callback_store.latest_sync_token()
    if latest is None:
        raise HTTPException(status_code=404, detail="还没有收到可用于 sync_msg 的回调 token/open_kfid")

    token, open_kfid = latest
    client = create_wecom_client_from_env()
    try:
        return await client.sync_messages(token=token, open_kfid=open_kfid, limit=limit)
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/messages/send-text")
async def send_text_message(request: SendTextMessageRequest) -> dict:
    client = create_wecom_client_from_env()
    try:
        return await client.send_text_message(
            touser=request.touser,
            open_kfid=request.open_kfid,
            content=request.content,
            msgid=request.msgid,
        )
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/messages/auto-reply")
async def auto_reply_messages(request: AutoReplyRequest) -> dict:
    try:
        return await _auto_reply_from_sync(
            token=request.token,
            open_kfid=request.open_kfid,
            cursor=request.cursor,
            limit=request.limit,
        )
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/messages/auto-reply-latest")
async def auto_reply_latest_messages(limit: int = Query(default=100, ge=1, le=1000)) -> dict:
    latest = callback_store.latest_sync_token()
    if latest is None:
        raise HTTPException(status_code=404, detail="还没有收到可用于自动回复的回调 token/open_kfid")

    token, open_kfid = latest
    try:
        return await _auto_reply_from_sync(token=token, open_kfid=open_kfid, limit=limit)
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/wecom/kf/callback", response_class=PlainTextResponse)
async def verify_callback(
    msg_signature: str,
    timestamp: str,
    nonce: str,
    echostr: str,
) -> str:
    try:
        crypto = create_callback_crypto_from_env()
        return crypto.verify_url(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr,
        )
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/wecom/kf/callback", response_class=PlainTextResponse)
async def receive_callback(
    request: Request,
    msg_signature: str,
    timestamp: str,
    nonce: str,
) -> str:
    raw_body = await request.body()
    try:
        crypto = create_callback_crypto_from_env()
        message = crypto.decrypt_callback_body(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            xml_body=raw_body,
        )
        callback_store.append(message)
        if _is_auto_reply_enabled() and message.get("Event") == "kf_msg_or_event":
            token = message.get("Token", "")
            open_kfid = message.get("OpenKfId", "")
            if token and open_kfid:
                await _auto_reply_from_sync(token=token, open_kfid=open_kfid)
        return "success"
    except WeComKFError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/wecom/kf/callbacks")
async def list_callbacks() -> dict[str, list[dict]]:
    """查看最近收到的回调内容。"""

    return {"items": callback_store.list()}


def _is_auto_reply_enabled() -> bool:
    return load_wecom_settings().auto_reply_enabled


async def _auto_reply_from_sync(
    *,
    token: str,
    open_kfid: str,
    cursor: str | None = None,
    limit: int = 100,
) -> dict:
    client = create_wecom_client_from_env()
    sync_result = await client.sync_messages(
        token=token,
        open_kfid=open_kfid,
        cursor=cursor,
        limit=limit,
    )

    replies: list[dict] = []
    skipped: list[dict] = []

    for item in sync_result.get("msg_list", []):
        msgid = item.get("msgid", "")
        msgtype = item.get("msgtype", "")
        external_userid = item.get("external_userid", "")
        item_open_kfid = item.get("open_kfid", "") or open_kfid

        if not msgid or processed_message_store.has(msgid):
            skipped.append({"msgid": msgid, "reason": "duplicate"})
            continue

        processed_message_store.add(msgid)

        if msgtype != "text":
            skipped.append({"msgid": msgid, "reason": f"unsupported_msgtype:{msgtype}"})
            continue

        text = item.get("text", {}) or {}
        user_message = text.get("content", "").strip()
        if not user_message:
            skipped.append({"msgid": msgid, "reason": "empty_text"})
            continue
        if not external_userid:
            skipped.append({"msgid": msgid, "reason": "missing_external_userid"})
            continue

        reply_text, citations = await answer_customer(
            conversation_id=f"wecom:{item_open_kfid}:{external_userid}",
            user_message=user_message,
        )
        send_result = await client.send_text_message(
            touser=external_userid,
            open_kfid=item_open_kfid,
            content=reply_text,
        )
        replies.append(
            {
                "msgid": msgid,
                "touser": external_userid,
                "open_kfid": item_open_kfid,
                "request_text": user_message,
                "reply_text": reply_text,
                "citation_count": len(citations),
                "send_result": send_result,
            }
        )

    return {
        "sync_result": {
            "next_cursor": sync_result.get("next_cursor"),
            "has_more": sync_result.get("has_more"),
            "msg_count": len(sync_result.get("msg_list", [])),
        },
        "auto_reply_enabled": _is_auto_reply_enabled(),
        "replies": replies,
        "skipped": skipped,
    }
