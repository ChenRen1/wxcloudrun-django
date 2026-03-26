"""Django URL 配置。"""

from django.urls import re_path

from wxcloudrun import views


urlpatterns = (
    re_path(r"^api/count/?$", views.counter),
    re_path(r"^health/?$", views.health),
    re_path(r"^api/agent/answer/?$", views.agent_answer),
    re_path(r"^wecom/kf/accounts/?$", views.wecom_create_account),
    re_path(r"^wecom/kf/messages/sync/?$", views.wecom_sync_messages),
    re_path(r"^wecom/kf/messages/sync-latest/?$", views.wecom_sync_latest_messages),
    re_path(r"^wecom/kf/messages/send-text/?$", views.wecom_send_text_message),
    re_path(r"^wecom/kf/messages/auto-reply-latest/?$", views.wecom_auto_reply_latest),
    re_path(r"^wecom/kf/callback/?$", views.wecom_callback),
    re_path(r"^wecom/kf/callbacks/?$", views.wecom_list_callbacks),
    re_path(r"^$", views.index),
)
