"""Django 视图。"""

from __future__ import annotations

import json
import logging

from asgiref.sync import async_to_sync
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from app.src.agent.service import answer_customer
from app.src.wecom.client import (
    CallbackStore,
    ProcessedMessageStore,
    WeComKFError,
    create_callback_crypto_from_env,
    create_wecom_client_from_env,
)
from wxcloudrun.models import Counters


logger = logging.getLogger("log")
callback_store = CallbackStore()
processed_message_store = ProcessedMessageStore()


def index(request: HttpRequest):
    return render(request, "index.html")


def health(request: HttpRequest):
    return JsonResponse({"status": "ok"}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def counter(request: HttpRequest):
    rsp = JsonResponse({"code": 0, "errorMsg": ""}, json_dumps_params={"ensure_ascii": False})
    if request.method in {"GET", "get"}:
        rsp = get_count()
    elif request.method in {"POST", "post"}:
        rsp = update_count(request)
    else:
        rsp = JsonResponse({"code": -1, "errorMsg": "请求方式错误"}, json_dumps_params={"ensure_ascii": False})
    logger.info("response result: %s", rsp.content.decode("utf-8"))
    return rsp


def get_count():
    try:
        data = Counters.objects.get(id=1)
    except Counters.DoesNotExist:
        return JsonResponse({"code": 0, "data": 0}, json_dumps_params={"ensure_ascii": False})
    return JsonResponse({"code": 0, "data": data.count}, json_dumps_params={"ensure_ascii": False})


def update_count(request: HttpRequest):
    logger.info("update_count req: %s", request.body)
    body = json.loads(request.body.decode("utf-8"))

    if "action" not in body:
        return JsonResponse({"code": -1, "errorMsg": "缺少action参数"}, json_dumps_params={"ensure_ascii": False})

    if body["action"] == "inc":
        try:
            data = Counters.objects.get(id=1)
        except Counters.DoesNotExist:
            data = Counters()
        data.id = 1
        data.count += 1
        data.save()
        return JsonResponse({"code": 0, "data": data.count}, json_dumps_params={"ensure_ascii": False})

    if body["action"] == "clear":
        try:
            data = Counters.objects.get(id=1)
            data.delete()
        except Counters.DoesNotExist:
            logger.info("record not exist")
        return JsonResponse({"code": 0, "data": 0}, json_dumps_params={"ensure_ascii": False})

    return JsonResponse({"code": -1, "errorMsg": "action参数错误"}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def agent_answer(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)

    body = json.loads(request.body.decode("utf-8") or "{}")
    conversation_id = body.get("conversation_id", "django-demo")
    user_message = (body.get("content") or "").strip()
    if not user_message:
        return JsonResponse({"detail": "content is required"}, status=400)

    reply, citations = async_to_sync(answer_customer)(conversation_id, user_message)
    return JsonResponse(
        {
            "reply": reply,
            "citations": [
                {
                    "id": item.id,
                    "title": item.title,
                    "source": item.source,
                    "content": item.content,
                    "score": item.score,
                }
                for item in citations
            ],
        },
        json_dumps_params={"ensure_ascii": False},
    )


@csrf_exempt
def wecom_create_account(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)
    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        result = async_to_sync(create_wecom_client_from_env().create_account)(
            name=body.get("name", ""),
            media_id=body.get("media_id", ""),
        )
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def wecom_sync_messages(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)
    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        result = async_to_sync(create_wecom_client_from_env().sync_messages)(
            token=body.get("token", ""),
            open_kfid=body.get("open_kfid", ""),
            cursor=body.get("cursor"),
            limit=int(body.get("limit", 100)),
            voice_format=int(body.get("voice_format", 0)),
        )
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def wecom_sync_latest_messages(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)
    latest = callback_store.latest_sync_token()
    if latest is None:
        return JsonResponse({"detail": "还没有收到可用于 sync_msg 的回调 token/open_kfid"}, status=404)

    token, open_kfid = latest
    limit = int(request.GET.get("limit", "100"))
    try:
        result = async_to_sync(create_wecom_client_from_env().sync_messages)(
            token=token,
            open_kfid=open_kfid,
            limit=limit,
        )
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def wecom_send_text_message(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)
    body = json.loads(request.body.decode("utf-8") or "{}")
    try:
        result = async_to_sync(create_wecom_client_from_env().send_text_message)(
            touser=body.get("touser", ""),
            open_kfid=body.get("open_kfid", ""),
            content=body.get("content", ""),
            msgid=body.get("msgid"),
        )
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def wecom_auto_reply_latest(request: HttpRequest):
    if request.method != "POST":
        return JsonResponse({"detail": "method not allowed"}, status=405)
    latest = callback_store.latest_sync_token()
    if latest is None:
        return JsonResponse({"detail": "还没有收到可用于自动回复的回调 token/open_kfid"}, status=404)
    token, open_kfid = latest
    limit = int(request.GET.get("limit", "100"))
    try:
        result = async_to_sync(_auto_reply_from_sync)(token=token, open_kfid=open_kfid, limit=limit)
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return JsonResponse(result, json_dumps_params={"ensure_ascii": False})


def wecom_verify_callback(request: HttpRequest):
    try:
        crypto = create_callback_crypto_from_env()
        result = crypto.verify_url(
            msg_signature=request.GET.get("msg_signature", ""),
            timestamp=request.GET.get("timestamp", ""),
            nonce=request.GET.get("nonce", ""),
            echostr=request.GET.get("echostr", ""),
        )
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return HttpResponse(result, content_type="text/plain; charset=utf-8")


@csrf_exempt
def wecom_receive_callback(request: HttpRequest):
    try:
        crypto = create_callback_crypto_from_env()
        message = crypto.decrypt_callback_body(
            msg_signature=request.GET.get("msg_signature", ""),
            timestamp=request.GET.get("timestamp", ""),
            nonce=request.GET.get("nonce", ""),
            xml_body=request.body,
        )
        callback_store.append(message)
        if _is_auto_reply_enabled() and message.get("Event") == "kf_msg_or_event":
            token = message.get("Token", "")
            open_kfid = message.get("OpenKfId", "")
            if token and open_kfid:
                async_to_sync(_auto_reply_from_sync)(token=token, open_kfid=open_kfid)
    except WeComKFError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)
    return HttpResponse("success", content_type="text/plain; charset=utf-8")


def wecom_list_callbacks(request: HttpRequest):
    return JsonResponse({"items": callback_store.list()}, json_dumps_params={"ensure_ascii": False})


@csrf_exempt
def wecom_callback(request: HttpRequest):
    if request.method == "GET":
        return wecom_verify_callback(request)
    if request.method == "POST":
        return wecom_receive_callback(request)
    return JsonResponse({"detail": "method not allowed"}, status=405)


def _is_auto_reply_enabled() -> bool:
    from app.src.wecom.config import load_wecom_settings

    return load_wecom_settings().auto_reply_enabled


async def _auto_reply_from_sync(*, token: str, open_kfid: str, cursor: str | None = None, limit: int = 100) -> dict:
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

        user_message = ((item.get("text", {}) or {}).get("content") or "").strip()
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
