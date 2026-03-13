"""
微信相关服务。

本模块提供封装好的微信相关接口，主要包含以下功能：
1. **获取微信 Access Token**: 获取调用微信接口凭证，包含一个简单的内存缓存（有效时长2小时减5分钟缓冲）。
2. **发送小程序订阅消息**: 向指定 openid 用户的微信发送“审核结果通知”订阅模板消息。
"""

import json
import time
import urllib.request
import urllib.parse
from flask import current_app

from utils.miniprogram_auth import get_mini_appid, get_mini_secret
import os

WX_TOKEN_URL = 'https://api.weixin.qq.com/cgi-bin/token'
WX_SEND_MESSAGE_URL = 'https://api.weixin.qq.com/cgi-bin/message/subscribe/send'

# 简单的内存缓存
_access_token_cache = {
    'token': None,
    'expires_at': 0
}

def get_wechat_template_id():
    """获取审核结果订阅消息的模板 ID"""
    return (os.getenv('WECHAT_MINI_TEMPLATE_ID', '') or '').strip()

def has_wechat_template_id():
    """是否已配置订阅消息模板 ID"""
    return bool(get_wechat_template_id())

def _fetch_access_token():
    """
    通过 HTTP 请求从微信服务器获取新的 app_token。
    """
    appid = get_mini_appid()
    secret = get_mini_secret()
    if not appid or not secret:
        raise ValueError('未配置 WECHAT_MINI_APPID 或 WECHAT_MINI_SECRET')

    query = urllib.parse.urlencode({
        'grant_type': 'client_credential',
        'appid': appid,
        'secret': secret
    })
    url = f"{WX_TOKEN_URL}?{query}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            payload = response.read().decode('utf-8')
            data = json.loads(payload)
    except Exception as err:
        raise RuntimeError(f'请求微信获取 token 接口失败: {str(err)}')

    if 'access_token' in data:
        token = data['access_token']
        expires_in = data.get('expires_in', 7200)
        # 提前 5 分钟 (300 秒) 让缓存失效
        expires_at = time.time() + max(0, expires_in - 300)
        
        _access_token_cache['token'] = token
        _access_token_cache['expires_at'] = expires_at
        return token
    else:
        errcode = data.get('errcode')
        errmsg = data.get('errmsg', '')
        raise RuntimeError(f'获取微信 access_token 失败: [{errcode}] {errmsg}')

def get_access_token(force_refresh=False):
    """
    获取微信接口调用凭证 (Access Token)。
    使用内存缓存，如果过期或强制重刷则重新获取。
    """
    now = time.time()
    if force_refresh or not _access_token_cache['token'] or _access_token_cache['expires_at'] < now:
        _fetch_access_token()
    
    return _access_token_cache['token']

def send_review_result_message(openid, student_name, action, page_path="pages/index/index"):
    """
    发送模板消息（审核结果通知）。
    不会抛出异常以防止阻断审核流程，如果失败仅打印日志。
    
    已知限制：需在微信后台找到或申请一个“审核结果通知”的模板。
    假设模板包含以下字段：
      - name10: 姓名
      - phrase5: 审核结果 (限制中英文、数字)
      - date7: 审核时间
      - thing11: 备注
    
    参数:
        openid (str): 学员的小程序 openid
        student_name (str): 学员姓名
        action (str): 操作结果，如 '已通过', '已驳回'
        page_path (str): 点击消息后跳转的小程序页面路径
    """
    template_id = get_wechat_template_id()
    if not template_id:
        current_app.logger.info("未配置 WECHAT_MINI_TEMPLATE_ID，跳过发送订阅消息。")
        return False
    
    if not openid:
        current_app.logger.warning("该学员没有关联提交者 openid，无法发送微信推送消息。")
        return False

    try:
        token = get_access_token()
    except Exception as e:
        current_app.logger.error(f"发送订阅消息失败，无法获取 token: {str(e)}")
        return False

    url = f"{WX_SEND_MESSAGE_URL}?access_token={token}"
    
    # 截断数据以防不合规 (name 最大一般较短，10个字符安全)
    safe_name = str(student_name)[:10] if student_name else '未知学员'
    safe_action = "通过" if "通过" in action else "驳回" 
    
    import datetime
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

    # 注意：这里的 data 结构必须严格符合模板后台的数据格式，否则会报错 47003
    # 示例格式
    # name10: 姓名, phrase5: 审核结果, date7: 审核时间, thing11: 备注
    payload = {
        "touser": openid,
        "template_id": template_id,
        "page": page_path,
        "miniprogram_state": current_app.config.get('MINIPROGRAM_STATE', 'release'),  # 可以配置 developer, trial, release
        "lang": "zh_CN",
        "data": {
            "name10": {
                "value": safe_name
            },
            "phrase5": {
                "value": safe_action
            },
            "date7": {
                "value": now_str
            },
            "thing11": {
                "value": "点击前往小程序查看详情"
            }
        }
    }
    
    data_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=data_bytes, headers={'Content-Type': 'application/json'})
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_content = response.read().decode('utf-8')
            res_data = json.loads(res_content)
            errcode = res_data.get('errcode', 0)
            if errcode == 0:
                current_app.logger.info(f"成功发送订阅消息给用户: {openid}, 状态: {action}")
                return True
            else:
                errmsg = res_data.get('errmsg', '')
                current_app.logger.warning(f"发送订阅消息失败 [{errcode}] {errmsg} (openid: {openid})")
                
                # 如果是 access_token 错误可能需要刷新并重试（简单的容错）
                if errcode in [40001, 40014, 42001]:
                    current_app.logger.info("尝试刷新 access_token 并重试...")
                    get_access_token(force_refresh=True)
                    # 避免无限循环，此处不再尝试，只记录结果
                
                return False
                
    except Exception as e:
        current_app.logger.error(f"发送订阅消息请求异常: {str(e)}")
        return False

def broadcast_new_student_to_admins(student_name):
    """
    向所有配置的小程序管理员发送新学员提交通知。
    复用审核结果通知的模板，将 action 写为 '新提交等待审核'。
    注意：这要求管理员用户在小程序端也授权过该订阅消息模板，否则微信接口会下发拦截（这属于正常现象）。
    """
    from utils.miniprogram_auth import parse_admin_openids
    admin_openids = parse_admin_openids()
    
    if not admin_openids:
        current_app.logger.info("未配置管理员 openid (TRAINING_SYSTEM_ADMIN_OPENIDS)，跳过发送新提交通知。")
        return
        
    current_app.logger.info(f"准备向 {len(admin_openids)} 位管理员推送新提交通知...")
    success_count = 0
    fail_count = 0
    
    # 复用 send_review_result_message 发送，action 显示为 "待审核"
    # template 限制："通过" or "驳回"。如果模板强校验，这里写 "待审核" 可能依然被接受（因为是中英文数字），
    # 我们测试直接发 "待审核"
    action_text = "待审核"
    
    for admin_openid in admin_openids:
        # 管理员点击卡片后，跳转到他自己的首页或者指定的审核列表页（当前用首页即可，首页有管理员入口）
        result = send_review_result_message(
            openid=admin_openid,
            student_name=student_name,
            action=action_text,
            page_path="pages/index/index" 
        )
        if result:
            success_count += 1
        else:
            fail_count += 1
            
    current_app.logger.info(f"管理员推送结束：成功 {success_count}，失败 {fail_count}。如果失败，可能是管理员未在小程序端授权接收该提醒。")
