"""
企业微信推送服务。

该模块封装了调用企业微信 API 获取 token 和发送消息的功能。
主要用于在有新学员提交信息时，向指定的内部管理员推送通知卡片。
"""

import json
import time
import urllib.request
import urllib.parse
from flask import current_app
import os

WECOM_TOKEN_URL = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
WECOM_SEND_MESSAGE_URL = 'https://qyapi.weixin.qq.com/cgi-bin/message/send'

# 简单的内存缓存
_wecom_token_cache = {
    'token': None,
    'expires_at': 0
}

def get_wecom_config():
    """获取企业微信的相关配置"""
    return {
        'corpid': (os.getenv('WX_CORPID', '') or '').strip(),
        'corpsecret': (os.getenv('WX_CORPSECRET', '') or '').strip(),
        'agentid': (os.getenv('WX_AGENTID', '') or '').strip(),
        'touser': (os.getenv('WX_TOUSER', '') or '').strip()
    }

def has_wecom_config():
    """是否已完整配置企业微信推送"""
    conf = get_wecom_config()
    return bool(conf['corpid'] and conf['corpsecret'] and conf['agentid'] and conf['touser'])

def _fetch_wecom_access_token():
    """从企业微信服务器获取 access_token"""
    conf = get_wecom_config()
    if not conf['corpid'] or not conf['corpsecret']:
        raise ValueError('未配置 WX_CORPID 或 WX_CORPSECRET')

    query = urllib.parse.urlencode({
        'corpid': conf['corpid'],
        'corpsecret': conf['corpsecret']
    })
    url = f"{WECOM_TOKEN_URL}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = response.read().decode('utf-8')
            data = json.loads(payload)
    except Exception as err:
        raise RuntimeError(f'请求企业微信获取 token 接口失败: {str(err)}')

    if data.get('errcode', 0) == 0 and 'access_token' in data:
        token = data['access_token']
        expires_in = data.get('expires_in', 7200)
        # 提前 5 分钟 (300 秒) 让缓存失效
        expires_at = time.time() + max(0, expires_in - 300)
        
        _wecom_token_cache['token'] = token
        _wecom_token_cache['expires_at'] = expires_at
        return token
    else:
        errcode = data.get('errcode')
        errmsg = data.get('errmsg', '')
        raise RuntimeError(f'获取企业微信 access_token 失败: [{errcode}] {errmsg}')

def get_wecom_access_token(force_refresh=False):
    """
    获取企业微信接口调用凭证 (Access Token)。
    使用内存缓存，如果过期或强制重刷则重新获取。
    """
    now = time.time()
    if force_refresh or not _wecom_token_cache['token'] or _wecom_token_cache['expires_at'] < now:
        _fetch_wecom_access_token()
    
    return _wecom_token_cache['token']

def send_new_student_notification(student_name, training_type, id_card, phone):
    """
    发送新学员提交通知到企业微信。
    不会抛出异常以防止阻断提交流程，如果失败仅打印日志。
    """
    conf = get_wecom_config()
    if not has_wecom_config():
        current_app.logger.info("未完整配置企业微信推送相关环境变量，跳过发送提交通知。")
        return False

    try:
        token = get_wecom_access_token()
    except Exception as e:
        current_app.logger.error(f"发送企业微信通知失败，无法获取 token: {str(e)}")
        return False

    url = f"{WECOM_SEND_MESSAGE_URL}?access_token={token}"
    
    import datetime
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 将拼音标识转为中文名以便展示
    training_type_name = "特种作业" if training_type == "special_operation" else "特种设备"
    if training_type not in ["special_operation", "special_equipment"]:
        training_type_name = training_type

    text_content = (
        f"【收到新学员报名提交】\n"
        f"姓名: {student_name}\n"
        f"项目: {training_type_name}\n"
        f"身份证: {id_card}\n"
        f"电话: {phone}\n"
        f"时间: {now_str}\n\n"
        f"请及时登录管理后台审核"
    )

    payload = {
        "touser": conf['touser'],
        "msgtype": "text",
        "agentid": int(conf['agentid']),
        "text": {
            "content": text_content
        },
        "enable_duplicate_check": 0
    }
    
    data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_content = response.read().decode('utf-8')
            res_data = json.loads(res_content)
            errcode = res_data.get('errcode', 0)
            if errcode == 0:
                current_app.logger.info(f"成功发送企业微信新提交通知，学员: {student_name}")
                return True
            else:
                errmsg = res_data.get('errmsg', '')
                current_app.logger.warning(f"发送企业微信通知失败 [{errcode}] {errmsg}")
                
                # token问题容错重试一把
                if errcode in [40014, 42001]:
                    current_app.logger.info("企业微信 token 试探性重刷...")
                    get_wecom_access_token(force_refresh=True)
                
                return False
                
    except Exception as e:
        current_app.logger.error(f"发送企业微信通知请求异常: {str(e)}")
        return False
