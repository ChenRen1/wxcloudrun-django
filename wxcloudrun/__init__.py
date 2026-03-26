"""微信云托管 Django 应用包。"""

import pymysql


# 微信云托管模板默认使用 PyMySQL 作为 MySQL 驱动，
# 这里在 Django 启动阶段提前注册，避免线上连接 MySQL 时才报错。
pymysql.install_as_MySQLdb()
