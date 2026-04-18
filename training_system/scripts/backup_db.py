#!/usr/bin/env python3
"""
数据库定时备份脚本。

功能：
  1. 将 SQLite 数据库安全复制到本地备份目录（带时间戳）
  2. 如果配置了 COS，自动上传到腾讯云 COS
  3. 自动清理超过保留天数的本地旧备份

用法：
  python backup_db.py               # 手动执行
  配合 cron 定时执行（见下方说明）

cron 配置示例（每天凌晨 3 点执行）：
  0 3 * * * cd /path/to/training_system && python scripts/backup_db.py >> logs/backup.log 2>&1

环境变量（可选，配置后自动上传到 COS）：
  COS_SECRET_ID, COS_SECRET_KEY, COS_REGION, COS_BUCKET
"""
import os
import sys
import shutil
import sqlite3
from datetime import datetime, timedelta

# 项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'database', 'students.db')
BACKUP_DIR = os.path.join(BASE_DIR, 'database', 'backups')
RETENTION_DAYS = 30  # 本地备份保留天数


def log(msg):
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] {msg}')


def backup_local():
    """使用 SQLite 在线备份 API 安全复制数据库（不会锁定正在使用的数据库）。"""
    if not os.path.exists(DB_PATH):
        log(f'❌ 数据库文件不存在: {DB_PATH}')
        return None

    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'students_{timestamp}.db'
    backup_path = os.path.join(BACKUP_DIR, backup_filename)

    # 使用 SQLite backup API（安全，即使数据库正在使用也不会损坏）
    src = sqlite3.connect(DB_PATH)
    dst = sqlite3.connect(backup_path)
    try:
        src.backup(dst)
        log(f'✅ 本地备份完成: {backup_path}')
        log(f'   大小: {os.path.getsize(backup_path) / 1024:.1f} KB')
        return backup_path
    finally:
        dst.close()
        src.close()


def upload_to_cos(backup_path):
    """上传备份到 COS（如果配置了 COS 环境变量）。"""
    # 加载 .env
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

    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
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
        log(f'🗑️  已清理 {removed} 个超过 {RETENTION_DAYS} 天的旧备份')


def main():
    log('===== 数据库备份开始 =====')

    # 1. 本地备份
    backup_path = backup_local()
    if not backup_path:
        log('❌ 备份失败，退出')
        sys.exit(1)

    # 2. 上传 COS
    upload_to_cos(backup_path)

    # 3. 清理旧备份
    cleanup_old_backups()

    log('===== 备份任务完成 =====\n')


if __name__ == '__main__':
    main()
