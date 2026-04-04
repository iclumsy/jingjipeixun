"""
批量修复 COS 上已有文件的 Content-Disposition 和 Content-Type 元数据。

不重新上传文件内容，仅通过 COS 服务端 copy-to-self 更新元数据（速度快）。

使用方法：
    # 在 training_system 目录下执行：
    python scripts/fix_cos_headers.py

    # 仅预览将要处理的文件，不实际操作：
    python scripts/fix_cos_headers.py --dry-run

    # 指定前缀（只修复某个子目录）：
    python scripts/fix_cos_headers.py --prefix students/特种设备-XX公司-张三/
"""
import os
import sys
import argparse
import mimetypes

_script_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_script_dir)
sys.path.insert(0, _project_root)


def load_env(base_dir):
    env_file = os.path.join(base_dir, '.env')
    if not os.path.exists(env_file):
        return
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            if line.startswith('export '):
                line = line[7:].strip()
            key, val = line.split('=', 1)
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


def get_cos_client():
    from qcloud_cos import CosConfig, CosS3Client
    secret_id  = os.getenv('COS_SECRET_ID', '')
    secret_key = os.getenv('COS_SECRET_KEY', '')
    region     = os.getenv('COS_REGION', '')
    bucket     = os.getenv('COS_BUCKET', '')

    if not all([secret_id, secret_key, region, bucket]):
        print('错误：COS 配置不完整')
        sys.exit(1)

    config = CosConfig(Region=region, SecretId=secret_id, SecretKey=secret_key)
    return CosS3Client(config), bucket, region, os.getenv('COS_KEY_PREFIX', '').strip().rstrip('/')


def list_all_objects(client, bucket, prefix):
    """列举指定前缀下所有 COS 对象。"""
    objects = []
    marker = ''
    while True:
        resp = client.list_objects(
            Bucket=bucket,
            Prefix=prefix,
            Marker=marker,
            MaxKeys=1000,
        )
        for obj in resp.get('Contents', []) or []:
            objects.append(obj['Key'])
        if resp.get('IsTruncated') == 'true':
            marker = resp.get('NextMarker', '')
        else:
            break
    return objects


def fix_object_headers(client, bucket, region, full_key, dry_run=False):
    """
    使用 copy-to-self 更新对象元数据（不重新传内容）。
    """
    content_type, _ = mimetypes.guess_type(full_key)
    if not content_type:
        content_type = 'application/octet-stream'

    if dry_run:
        print(f'[DRY] {full_key}  →  Content-Type={content_type}  Content-Disposition=inline')
        return True

    try:
        client.copy_object(
            Bucket=bucket,
            Key=full_key,
            CopySource={
                'Bucket': bucket,
                'Key': full_key,
                'Region': region,
            },
            # Replaced 表示使用下方指定的 Header，而非保留源对象的 Header
            MetadataDirective='Replaced',
            ContentType=content_type,
            ContentDisposition='inline',
        )
        return True
    except Exception as e:
        print(f'[FAIL] {full_key}: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='批量修复 COS 文件的 Content-Disposition 元数据')
    parser.add_argument('--dry-run', action='store_true', help='仅预览，不实际操作')
    parser.add_argument('--prefix', default='students/', help='限定处理的前缀（默认 students/）')
    args = parser.parse_args()

    load_env(_project_root)
    client, bucket, region, global_prefix = get_cos_client()

    cos_prefix = f'{global_prefix}/{args.prefix}'.lstrip('/') if global_prefix else args.prefix

    print(f'COS 桶：{bucket}  区域：{region}')
    print(f'扫描前缀：{cos_prefix}')
    if args.dry_run:
        print('--- DRY-RUN 模式，不实际修改 ---')
    print()

    print('正在列举对象...')
    keys = list_all_objects(client, bucket, cos_prefix)
    print(f'共找到 {len(keys)} 个对象')
    print()

    ok, fail = 0, 0
    for i, key in enumerate(keys, 1):
        success = fix_object_headers(client, bucket, region, key, dry_run=args.dry_run)
        if not args.dry_run:
            status = 'OK  ' if success else 'FAIL'
            print(f'[{status}] ({i}/{len(keys)}) {key}')
        if success:
            ok += 1
        else:
            fail += 1

    print()
    print('=' * 60)
    if args.dry_run:
        print(f'DRY-RUN 完成：将处理 {ok} 个对象')
    else:
        print(f'修复完成：成功 {ok} 个  失败 {fail} 个')
    print('=' * 60)


if __name__ == '__main__':
    main()
