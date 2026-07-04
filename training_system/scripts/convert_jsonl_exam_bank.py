#!/usr/bin/env python3
"""
Convert Junrui-style JSONL exam questions into the JSON format accepted by
the backend exam-bank uploader, and download referenced images.

Example:
  python3 training_system/scripts/convert_jsonl_exam_bank.py \
    "/Users/ditto/Documents/junrui/特种设备安全管理(A)_起重机械.jsonl" \
    --output training_system/static/data/A_起重机械安全管理.json \
    --image-dir training_system/static/images/junrui \
    --image-base-url http://file.tskspx.cn \
    --image-prefix qizhongjixie_
"""

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request


IMG_RE = re.compile(r'<img\b[^>]*\bsrc\s*=\s*([\'"]?)([^\'"\s>]+)\1[^>]*>', re.I)
TAG_RE = re.compile(r'<[^>]+>')


def _clean_text(value):
    value = IMG_RE.sub('[图片]', str(value or ''))
    value = TAG_RE.sub('', value)
    return html.unescape(value).strip()


def _type_code(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return raw


def _normalize_answer(answer, type_code=None):
    if isinstance(answer, list):
        parts = []
        for item in answer:
            parts.extend(_normalize_answer(item, type_code))
        return parts
    if isinstance(answer, bool):
        return ['A' if answer else 'B']

    text = str(answer or '').strip().upper()
    if not text:
        return []

    if ',' in text or '，' in text or '、' in text:
        return [part.strip() for part in re.split(r'[,，、]', text) if part.strip()]

    if _type_code(type_code) == 2 and len(text) > 1 and re.fullmatch(r'[A-Z]+', text):
        return list(text)

    return [text]


def _source_id(item):
    return item.get('stbh') or item.get('id') or item.get('source_apid') or ''


def _question_type(item):
    type_name = str(item.get('stlx_name') or item.get('type') or '').strip()
    if type_name:
        return type_name
    code = _type_code(item.get('stlx') if 'stlx' in item else item.get('type_code'))
    if code in (0, 3):
        return '判断题'
    if code == 2:
        return '多选题'
    return '单选题'


def _image_srcs(value):
    return [match.group(2).strip() for match in IMG_RE.finditer(str(value or '')) if match.group(2).strip()]


def _safe_filename(name):
    name = urllib.parse.unquote(os.path.basename(name or '')).strip()
    name = re.sub(r'[^0-9A-Za-z._-]+', '_', name)
    return name or 'image.jpg'


def _filename_for_src(src, image_prefix, used_names):
    parsed = urllib.parse.urlparse(src)
    base = _safe_filename(parsed.path or src)
    candidate = f'{image_prefix}{base}'
    stem, ext = os.path.splitext(candidate)
    counter = 2
    while candidate in used_names:
        candidate = f'{stem}_{counter}{ext}'
        counter += 1
    used_names.add(candidate)
    return candidate


def _full_image_url(src, image_base_url):
    if re.match(r'^https?://', src, re.I):
        return src
    base = (image_base_url or '').rstrip('/')
    path = src if src.startswith('/') else f'/{src}'
    return f'{base}{path}' if base else path


def download_image(url, dest_path):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
        content_type = response.headers.get('Content-Type', '')
    if not data:
        raise RuntimeError(f'empty image response: {url}')
    if content_type and 'image' not in content_type.lower():
        raise RuntimeError(f'unexpected content type {content_type}: {url}')
    with open(dest_path, 'wb') as fp:
        fp.write(data)


def _load_jsonl(input_path):
    rows = []
    with open(input_path, encoding='utf-8-sig') as fp:
        for line_no, line in enumerate(fp, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as err:
                raise ValueError(f'第 {line_no} 行 JSON 无效: {err}') from err
    return rows


def convert_jsonl(
    input_path,
    output_path,
    image_dir,
    image_prefix='',
    image_base_url='',
    downloader=download_image,
):
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)

    rows = _load_jsonl(input_path)
    used_names = set()
    image_map = {}
    output = []
    download_count = 0

    def resolve_image(src):
        nonlocal download_count
        if src not in image_map:
            filename = _filename_for_src(src, image_prefix, used_names)
            dest_path = os.path.join(image_dir, filename)
            downloader(_full_image_url(src, image_base_url), dest_path)
            image_map[src] = filename
            download_count += 1
        return image_map[src]

    for item in rows:
        raw_type_code = item.get('stlx') if 'stlx' in item else item.get('type_code')
        type_code = _type_code(raw_type_code)
        question_html = str(item.get('question') or item.get('question_html') or '')
        question_images = [resolve_image(src) for src in _image_srcs(question_html)]

        options = {}
        option_images = {}
        for key, value in (item.get('options') or {}).items():
            key = str(key).strip().upper()
            option_html = str(value or '')
            images = [resolve_image(src) for src in _image_srcs(option_html)]
            options[key] = _clean_text(option_html)
            if images:
                option_images[key] = images

        output.append({
            'id': _source_id(item),
            'type': _question_type(item),
            'type_code': type_code,
            'question': _clean_text(question_html),
            'question_html': question_html,
            'question_images': question_images,
            'options': options,
            'option_images': option_images,
            'answer': _normalize_answer(item.get('answer'), type_code),
            'analysis': str(item.get('analysis') or ''),
            'audio': str(item.get('audio') or ''),
            'source_apid': _source_id(item),
            'project': item.get('project') or {},
        })

    with open(output_path, 'w', encoding='utf-8') as fp:
        json.dump(output, fp, ensure_ascii=False, separators=(',', ':'))

    return {
        'questions': len(output),
        'image_refs': sum(len(q['question_images']) for q in output)
                      + sum(len(v) for q in output for v in q['option_images'].values()),
        'unique_images': len(image_map),
        'downloaded': download_count,
        'output_path': output_path,
        'image_dir': image_dir,
    }


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Convert JSONL exam bank to backend upload JSON.')
    parser.add_argument('input', help='source .jsonl file')
    parser.add_argument('--output', required=True, help='output .json file for backend upload')
    parser.add_argument(
        '--image-dir',
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'images', 'junrui'),
        help='directory where downloaded images are saved',
    )
    parser.add_argument('--image-base-url', default='http://file.tskspx.cn', help='base URL for relative image paths')
    parser.add_argument('--image-prefix', default='', help='prefix added before the original image filename')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    summary = convert_jsonl(
        args.input,
        args.output,
        args.image_dir,
        image_prefix=args.image_prefix,
        image_base_url=args.image_base_url,
    )
    print(
        '转换完成: '
        f'题目 {summary["questions"]} 道，'
        f'图片引用 {summary["image_refs"]} 个，'
        f'唯一图片 {summary["unique_images"]} 张'
    )
    print(f'JSON: {summary["output_path"]}')
    print(f'图片目录: {summary["image_dir"]}')


if __name__ == '__main__':
    main()
