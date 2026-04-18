#!/usr/bin/env python3
"""
数据库定时备份脚本。

支持两种运行方式：
  1. 命令行手动执行: python scripts/backup_db.py
  2. 被 Flask 应用内置调度器自动调用（无需 cron）

功能：
  - 使用 SQLite backup API 安全复制数据库（不锁定正在运行的数据库）
  - 如果配置了 COS，自动上传到腾讯云 COS
  - 自动清理超过保留天数的本地旧备份

环境变量（可选，配置后自动上传到 COS）：
  COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET

环境变量（备份调度，在 .env 中配置）：
  DB_BACKUP_HOUR=3        备份执行小时（0-23，默认 3 即凌晨 3 点）
  DB_BACKUP_KEEP_DAYS=30  本地备份保留天数（默认 30）
"""
import os
import sys
import sqlite3
from datetime import datetime, timedelta

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'students.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'database', 'backups')


def _get_retention_days():
    try:
        return max(1, int(os.getenv('DB_BACKUP_KEEP_DAYS', '30')))
    except (TypeError, ValueError):
        return 30


def log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] [backup] {msg}')


def backup_local(db_path=None):
    """使用 SQLite 在线备份 API 安全复制数据库。"""
    db_path = db_path or DB_PATH
    if not os.path.exists(db_path):
        log(f'❌ 数据库文件不存在: {db_path}')
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'students_{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
        size_kb = os.path.getsize(backup_path) / 1024
        log(f'✅ 本地备份完成: {backup_filename} ({size_kb:.1f} KB)')
        return backup_path
    finally:
        dst.close()
        src.close()


def upload_to_cos(backup_path):
    """上传备份到 COS（如果配置了 COS 环境变量）。"""
    secret_id = os.getenv('COS_SECRET_ID', '')
    secret_key = os.getenv('COS_SECRET_KEY', '')
    region = os.getenv('COS_REGION', '')
    bucket = os.getenv('COS_BUCKET', '')

    if not all([secret_id, secret_key, region, bucket]):
        log('⏭️  COS 未配置，跳过云端备份')
        return False

    try:
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
        client = CosS3Client(config)

        filename = os.path.basename(backup_path)
        prefix = os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/')
        cos_key = f'{prefix}/backups/{filename}' if prefix else f'backups/{filename}'

        with open(backup_path, 'rb') as f:
            client.put_object(Bucket=bucket, Body=f.read(), Key=cos_key)

        log(f'☁️  COS 上传成功: {cos_key}')
        return True
    except Exception as e:
        log(f'⚠️  COS 上传失败: {e}')
        return False


def cleanup_old_backups():
    """清理超过保留天数的本地备份。"""
    if not os.path.isdir(BACKUP_DIR):
        return

    retention_days = _get_retention_days()
    cutoff = datetime.now() - timedelta(days=retention_days)
    removed = 0
    for f in os.listdir(BACKUP_DIR):
        if not f.startswith('students_') or not f.endswith('.db'):
            continue
        fpath = os.path.join(BACKUP_DIR, f)
        mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
        if mtime < cutoff:
            os.remove(fpath)
            removed += 1

    if removed:
        log(f'🗑️  已清理 {removed} 个超过 {retention_days} 天的旧备份')


def run_backup(db_path=None):
    """执行完整备份流程（本地 + COS + 清理），供内部调度器和命令行共用。"""
    log('===== 数据库备份开始 =====')

    backup_path = backup_local(db_path)
    if not backup_path:
        log('❌ 备份失败')
        return False

    upload_to_cos(backup_path)
    cleanup_old_backups()

    log('===== 备份任务完成 =====')
    return True


# ======================== 内置调度器 ========================

_scheduler_started = False


def start_backup_scheduler(app):
    """
    在 Flask 应用内启动后台备份调度线程。

    使用 daemon 线程 + threading.Event 实现，
    无需任何第三方依赖，应用退出时线程自动销毁。
    """
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    import threading

    backup_hour = 3
    try:
        backup_hour = max(0, min(23, int(os.getenv('DB_BACKUP_HOUR', '3'))))
    except (TypeError, ValueError):
        pass

    db_path = app.config.get('DATABASE', DB_PATH)
    stop_event = threading.Event()

    def _scheduler_loop():
        while not stop_event.is_set():
            now = datetime.now()
            # 计算下一个备份时间点
            target = now.replace(hour=backup_hour, minute=0, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            app.logger.info(
                f'[backup] 下次备份时间: {target.strftime("%Y-%m-%d %H:%M")} '
                f'(约 {wait_seconds / 3600:.1f} 小时后)'
            )

            # 等待到目标时间，或被 stop_event 中断
            if stop_event.wait(timeout=wait_seconds):
                break  # 收到停止信号

            # 执行备份
            try:
                app.logger.info('[backup] 定时备份开始执行')
                run_backup(db_path)
                app.logger.info('[backup] 定时备份执行完成')
            except Exception as e:
                app.logger.error(f'[backup] 定时备份异常: {e}')

    t = threading.Thread(target=_scheduler_loop, name='db-backup-scheduler', daemon=True)
    t.start()
    app.logger.info(f'[backup] 内置备份调度器已启动，每天 {backup_hour}:00 自动备份')


# ======================== 命令行入口 ========================

if __name__ == '__main__':
    # 命令行手动执行时加载 .env
    env_file = os.path.join(BASE_DIR, '.env')
    if os.path.isfile(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if line.startswith('export '):
                    line = line[7:].strip()
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip('\'"')
                os.environ.setdefault(k, v)

    success = run_backup()
    sys.exit(0 if success else 1)
