#!/bin/sh

set -eu

PORT="${PORT:-80}"

# 容器启动时先补齐 Django 内置表与模板里的计数器表，
# 这样首次部署后接口可以直接工作。
python manage.py migrate --noinput

exec python manage.py runserver "0.0.0.0:${PORT}"
