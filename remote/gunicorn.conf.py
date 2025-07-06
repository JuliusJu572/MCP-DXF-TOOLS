# gunicorn.conf.py
# Gunicorn 配置文件

import multiprocessing
import os

# 服务器绑定地址
bind = "0.0.0.0:8000"

# 工作进程数
# 建议：CPU 核心数 * 2 + 1，或者通过环境变量设置
workers = 1

# 工作进程类型（异步）
worker_class = "uvicorn.workers.UvicornWorker"

# 连接相关
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100

# 超时设置
timeout = 300  # 5分钟超时，适合 DXF 处理
keepalive = 2
graceful_timeout = 30

# 预加载应用（提高性能，节省内存）
preload_app = True

# 日志配置
accesslog = "-"  # 输出到 stdout
errorlog = "-"   # 输出到 stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程管理
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# 重启设置
reload = False  # 生产环境设为 False
reload_engine = "auto"

# SSL（如果需要）
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# 其他设置
forwarded_allow_ips = "*"  # 允许所有代理
secure_scheme_headers = {
    "X-FORWARDED-PROTOCOL": "ssl",
    "X-FORWARDED-PROTO": "https",
    "X-FORWARDED-SSL": "on"
}