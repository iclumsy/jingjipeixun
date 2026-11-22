# -*- coding: utf-8 -*-
"""
Gunicorn 生产环境配置文件

针对当前服务器环境优化：
1. 内存控制：配置 worker 请求计数与生命周期回收，解决长期运行模型库/图像库带来的内存泄露问题。
2. 资源配比：根据 4核 CPU / 3.6GB 内存，搭配 2 workers + 2 threads，兼顾并发吞吐与内存安全。
3. 任务超时：适当拉长 timeout，防止材料生成/PDF合成耗时较长时被误杀。
"""
import os
import multiprocessing

# ======================== 网络绑定 ========================
# 监听地址与端口（保持与原有 app.py 一致）
bind = "0.0.0.0:5001"

# ======================== Worker 进程模型 ========================
# 模式选择：gthread（单进程多线程模式），相比纯多进程能大幅降低内存消耗
worker_class = "gthread"

# 进程数与线程数：
# 服务器物理内存约 3.6GB，且宿主机还运行其他 Python 服务（如 lottery 等）
# 推荐 2 个 worker，每个 worker 开启 2 个线程，支撑 4 个并发请求
workers = int(os.getenv("GUNICORN_WORKERS", 2))
threads = int(os.getenv("GUNICORN_THREADS", 2))

# 最大客户端并发连接数
worker_connections = 1000

# ======================== 核心防内存泄漏配置 ========================
# 每个 worker 处理满 1000 个请求后自动安全退出并重启，由主进程释放所有底层 C/C++ 内存（如 OpenCV/ONNX/WeasyPrint）
max_requests = 1000

# 抖动随机区间：防止所有 worker 恰好同时达到 1000 次请求并同时重启
max_requests_jitter = 100

# ======================== 超时配置 ========================
# 超时时间设为 120 秒（材料汇总、导出压缩包、PDF渲染可能超过默认的 30 秒）
timeout = 120
graceful_timeout = 30
keepalive = 5

# ======================== 日志配置 ========================
base_dir = os.path.dirname(os.path.abspath(__file__))
log_dir = os.path.join(base_dir, "logs")
os.makedirs(log_dir, exist_ok=True)

# 访问日志与错误日志路径
accesslog = os.path.join(log_dir, "gunicorn_access.log")
errorlog = os.path.join(log_dir, "gunicorn_error.log")
loglevel = "info"

# 是否捕获 Python 内部标准输出/错误（print 与 traceback）
capture_output = True

# ======================== 进程管理 ========================
# 是否后台守护运行：
# - 若在 screen / tmux / supervisor / systemd 中运行，请保持 False
# - 若独立在后台执行，可设为 True
daemon = False

