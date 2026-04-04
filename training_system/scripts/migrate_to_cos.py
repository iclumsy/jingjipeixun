"""
本地文件迁移到 COS 的一次性脚本。

使用场景：服务器上已有的学员附件需要全量同步至 COS。
新上传的附件从 dual 模式启动后会自动双写，无需此脚本。

使用方法：
    # 确保 .env 中已正确配置 COS_SECRET_ID / COS_KEY 等参数
    # 在 training_system 目录下执行：
    python scripts/migrate_to_cos.py

    # 仅预览，不实际上传（dry-run 模式）：
    python scripts/migrate_to_cos.py --dry-run

    # 指定特定子目录（如只同步某学员文件夹）：
    python scripts/migrate_to_cos.py --prefix 特种设备-XX公司-张三

选项：
    --dry-run       仅打印将要上传的文件列表，不执行上传
    --prefix TEXT   只同步 students/<prefix>/ 下的文件
    --skip-existing 跳过 COS 上已存在的文件（节省流量，默认跳过）
    --overwrite     强制覆盖 COS 上已存在的文件

统计：
    脚本结束时打印上传成功/跳过/失败数量，并将失败文件路径写入 migrate_failed.txt。
"""
import os
import sys
import argparse

# 将项目根目录加入 Python 路径（脚本在 scripts/ 子目录）
_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _project_root)


def load_env(base_dir):
    """加载 .env 文件。"""
    env_file = os.path.join(base_dir, '.env')
    if not os.path.exists(env_file):
        print(f'[警告] 未找到 .env 文件：{env_file}')
        return
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


def get_cos_client():
    """初始化 COS 客户端。"""
    from qcloud_cos import CosConfig, CosS3Client
    secret_id  = os.getenv('COS_SECRET_ID', '')
    secret_key = os.getenv('COS_SECRET_KEY', '')
    region     = os.getenv('COS_REGION', '')
    bucket     = os.getenv('COS_BUCKET', '')

    if not all([secret_id, secret_key, region, bucket]):
        print('错误：COS 配置不完整，请填写 .env 中的 COS_SECRET_ID / COS_SECRET_KEY / COS_REGION / COS_BUCKET')
        sys.exit(1)

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config), bucket, os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/')


def cos_key_exists(client, bucket, full_key):
    """检查 COS 对象是否存在。"""
    try:
        client.head_object(Bucket=bucket, Key=full_key)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description='将本地 students/ 目录迁移至腾讯 COS')
    parser.add_argument('--dry-run', action='store_true', help='仅打印文件列表，不实际上传')
    parser.add_argument('--prefix', default='', help='限定同步的子目录前缀（相对于 students/）')
    parser.add_argument('--overwrite', action='store_true', help='强制覆盖 COS 上已存在的文件')
    args = parser.parse_args()

    skip_existing = not args.overwrite
    base_dir = _project_root
    students_dir = os.path.join(base_dir, 'students')

    # 加载 .env
    load_env(base_dir)

    if args.dry_run:
        print('=' * 60)
        print('DRY-RUN 模式：仅预览，不实际上传')
        print('=' * 60)
    
    client, bucket, global_prefix = get_cos_client()

    # 确定要扫描的本地目录
    if args.prefix:
        scan_dir = os.path.join(students_dir, args.prefix)
        rel_prefix = f'students/{args.prefix}/'
    else:
        scan_dir = students_dir
        rel_prefix = 'students/'

    if not os.path.isdir(scan_dir):
        print(f'错误：目录不存在：{scan_dir}')
        sys.exit(1)

    print(f'扫描目录：{scan_dir}')
    print(f'COS 桶：{bucket}  区域：{os.getenv("COS_REGION")}')
    print(f'COS 前缀：{global_prefix or "(无)"}')
    print()

    # 收集所有文件
    all_files = []
    for root, dirs, filenames in os.walk(scan_dir):
        dirs.sort()
        for fn in sorted(filenames):
            if fn.startswith('.'):
                continue
            abs_path = os.path.join(root, fn)
            rel_key = os.path.relpath(abs_path, base_dir).replace('\\', '/')
            all_files.append((abs_path, rel_key))

    print(f'共找到 {len(all_files)} 个文件')
    print()

    stats = {'upload': 0, 'skip': 0, 'fail': 0}
    failed_files = []

    for i, (abs_path, rel_key) in enumerate(all_files, 1):
        full_key = f'{global_prefix}/{rel_key}' if global_prefix else rel_key

        # dry-run 仅打印
        if args.dry_run:
            print(f'[{i}/{len(all_files)}] {rel_key}  ->  {full_key}')
            stats['upload'] += 1
            continue

        # 跳过已存在的
        if skip_existing and cos_key_exists(client, bucket, full_key):
            print(f'[SKIP] {rel_key}')
            stats['skip'] += 1
            continue

        # 上传
        try:
            import mimetypes as _mt
            content_type, _ = _mt.guess_type(abs_path)
            if not content_type:
                content_type = 'application/octet-stream'
            with open(abs_path, 'rb') as f:
                client.put_object(
                    Bucket=bucket,
                    Body=f,
                    Key=full_key,
                    ContentType=content_type,
                    ContentDisposition='inline',
                )
            print(f'[OK  ] ({i}/{len(all_files)}) {rel_key}')
            stats['upload'] += 1
        except Exception as e:
            print(f'[FAIL] {rel_key}  ->  {e}')
            stats['fail'] += 1
            failed_files.append(rel_key)

    # 汇总
    print()
    print('=' * 60)
    if args.dry_run:
        print(f'DRY-RUN 完成：将上传 {stats["upload"]} 个文件')
    else:
        print(f'迁移完成：上传 {stats["upload"]} 个  跳过 {stats["skip"]} 个  失败 {stats["fail"]} 个')

    if failed_files:
        fail_log = os.path.join(_project_root, 'migrate_failed.txt')
        with open(fail_log, 'w', encoding='utf-8') as f:
            f.write('\n'.join(failed_files))
        print(f'失败文件列表已写入：{fail_log}')
    print('=' * 60)


if __name__ == '__main__':
    main()
