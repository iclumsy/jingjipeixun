import os
import base64
import requests
import logging
from flask import current_app

logger = logging.getLogger(__name__)

class JunruiServiceError(Exception):
    pass


# ======================== 本地系统 → 君瑞系统 名称映射 ========================
# 当本地系统的名称和君瑞系统不一致时，在此处添加映射。
# 匹配优先级：映射转换 → 精确匹配 → 模糊匹配（包含关系）

# job_category（作业种类）映射：本地名 → 君瑞 category text
CATEGORY_NAME_MAP = {
    '特种设备安全管理': '特种设备安全管理',          # category_id=01
    '锅炉作业': '锅炉作业',                         # category_id=02
    '压力容器作业': '压力容器作业',                   # category_id=03
    '起重机作业': '起重机作业',                       # category_id=07
    '场(厂)内专用机动车辆作业': '场(厂)内专用机动车辆作业',  # category_id=10
}

# exam_project（考试项目）映射：本地名 → 君瑞 project text
PROJECT_NAME_MAP = {
    # 安全管理类：本地拆分了多个子项目，君瑞只有一个统一的"特种设备安全管理"
    '电梯安全管理': '特种设备安全管理',               # project_id=0195
    '起重机械安全管理': '特种设备安全管理',           # project_id=0195
    '锅炉压力容器压力管道安全管理': '特种设备安全管理', # project_id=0195
    '场内机动车安全管理': '特种设备安全管理',         # project_id=0195
    # 锅炉类
    '工业锅炉司炉': '工业锅炉司炉',                 # project_id=0295
    '锅炉水处理': '锅炉水处理',                      # project_id=0297
    # 压力容器类
    '快开门式压力容器操作': '快开门式压力容器操作',   # project_id=0395
    # 起重机类：本地简称 vs 君瑞全称
    '起重机指挥': '起重机指挥',                       # project_id=0791
    '桥式起重机司机': '起重机司机(限桥式起重机)',     # project_id=0798
    '门式起重机司机': '起重机司机(限门式起重机)',     # project_id=0799
    # 场内车辆类
    '叉车司机': '叉车司机',                           # project_id=1095
    '观光车和观光列车司机': '观光车和观光列车司机',   # project_id=1096
}


class JunruiService:
    BASE_URL = "http://www.junruizx.com"

    def __init__(self):
        # 强制使用环境变量中的配置，避免硬编码明文密码
        self.username = os.environ.get("JUNRUI_USERNAME")
        self.password = os.environ.get("JUNRUI_PASSWORD")
        if not self.username or not self.password:
            logger.error("未配置君瑞系统相关环境变量 (JUNRUI_USERNAME / JUNRUI_PASSWORD)")
            raise JunruiServiceError("后台未配置开卡外接账号系统")

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "source": "web",
            "Accept": "application/json, text/plain, */*",
        })

    def login(self):
        """登录外部系统，获取并设置 Token"""
        url = f"{self.BASE_URL}/api/trainmanager/auth/loginWithPwdV2"
        pwd_b64 = base64.b64encode(self.password.encode('utf-8')).decode('utf-8')
        payload = {
            "userCode": self.username,
            "password": pwd_b64,
            "loginType": "1",
            "machineid": self.session.headers["User-Agent"],
            "needBindWeChat": 0
        }
        
        try:
            res = self.session.post(url, json=payload, timeout=10)
            res.raise_for_status()
            data = res.json()
            if data.get("code") != 200:
                raise JunruiServiceError(f"登录君瑞失败: {data.get('message', '未知错误')}")
            
            # token 应该在 entity 里
            entity = data.get("entity", {})
            token = entity.get("token") or data.get("token")
            if not token:
                raise JunruiServiceError("登录成功但未能解析出 Token")
            
            self.session.headers.update({"token": token})
            logger.info("成功登录君瑞系统获取 Token")
        except requests.RequestException as e:
            logger.error(f"君瑞登录接口请求异常: {e}")
            raise JunruiServiceError(f"请求君瑞登录接口失败: {str(e)}")

    def _get_api(self, uri, params=None):
        url = f"{self.BASE_URL}{uri}"
        res = self.session.get(url, params=params, timeout=10)
        res.raise_for_status()
        data = res.json()
        if data.get("code") != 200:
            raise JunruiServiceError(f"请求 {uri} 失败: {data.get('message')}")
        return data.get("entity", [])

    def get_category_id(self, job_category):
        """匹配行业大类 / 作业种类"""
        # 先尝试名称映射
        mapped = CATEGORY_NAME_MAP.get(job_category, job_category)
        if mapped != job_category:
            logger.info(f"作业种类名称映射: {job_category} -> {mapped}")

        logger.info(f"开始在外部系统匹配行业种类: {mapped}")
        if not mapped:
            raise JunruiServiceError("学员作业种类(job_category)为空，无法匹配")
        categories = self._get_api('/api/trainmanager/common/categories', {
            'industry': '02', 'projectType': '0', 'planType': '0'
        })
        available_names = [c.get("text", "") for c in categories]
        logger.info(f"外部系统返回的所有行业种类: {available_names}")

        # 精确匹配
        for c in categories:
            if c.get("text") == mapped:
                matched_id = c.get("value")
                logger.info(f"匹配行业种类精确成功: {mapped} -> category_id: {matched_id}")
                return matched_id
        # 降级：外部名称 包含在 本地名称中
        for c in categories:
            if c.get("text") and c.get("text") in mapped:
                matched_id = c.get("value")
                logger.info(f"匹配行业种类模糊成功: {mapped} -> 接近于 {c.get('text')} (category_id: {matched_id})")
                return matched_id
        # 降级：本地名称 包含在 外部名称中
        for c in categories:
            if c.get("text") and mapped in c.get("text"):
                matched_id = c.get("value")
                logger.info(f"匹配行业种类反向模糊成功: {mapped} -> {c.get('text')} (category_id: {matched_id})")
                return matched_id
        raise JunruiServiceError(f"无法在外部系统中匹配到行业类别: {job_category}（外部系统可用: {available_names}）")

    def get_project_id(self, category_id, exam_project):
        """匹配具体的作业项目 (如叉车司机 -> 1095)"""
        # 先尝试名称映射
        mapped = PROJECT_NAME_MAP.get(exam_project, exam_project)
        if mapped != exam_project:
            logger.info(f"考试项目名称映射: {exam_project} -> {mapped}")

        logger.info(f"开始在外部系统匹配考试项目: {mapped} (基于分类 {category_id})")
        if not mapped:
            raise JunruiServiceError("学员考试项目(exam_project)为空，无法匹配")
        projects = self._get_api('/api/trainmanager/common/projects', {
            'category': category_id, 'projectType': '0', 'planType': '0'
        })
        available_names = [p.get("text", "") for p in projects]
        logger.info(f"外部系统返回的所有考试项目: {available_names}")

        # 精确匹配
        for p in projects:
            if p.get("text") == mapped:
                matched_id = p.get("value")
                logger.info(f"匹配考试项目成功: {mapped} -> project_id: {matched_id}")
                return matched_id
        # 降级：包含关系匹配
        for p in projects:
            text = p.get("text", "")
            if text and (text in mapped or mapped in text):
                matched_id = p.get("value")
                logger.info(f"匹配考试项目模糊成功: {mapped} -> {text} (project_id: {matched_id})")
                return matched_id
        raise JunruiServiceError(f"无法在外部系统中找到对应的考试项目: {exam_project}（外部系统可用: {available_names}）")

    def get_plan_id(self, project_id, card_type="50"):
        """获取方案 planId (如价格 50)"""
        logger.info(f"开始匹配系统套餐/价格方案 (card_type): {card_type} (基于项目 {project_id})")
        prices = self._get_api('/api/trainmanager/common/prices', {
            'project': project_id, 'projectType': '0', 'planType': '0'
        })
        # 找对应的 text 为 "50" 的 value 作为 planId
        for p in prices:
            if p.get("text") == card_type:
                matched_id = p.get("value")
                logger.info(f"匹配套餐方案精确成功: {card_type} -> planId: {matched_id}")
                return matched_id
        # 如果找不到 "50"，默认取第一个
        if prices:
            matched_id = prices[0].get("value")
            logger.warning(f"未能精确匹配价格为 {card_type} 的方案，采用第一个可用方案: {prices[0].get('text')} -> planId: {matched_id}")
            return matched_id
        raise JunruiServiceError(f"在外部系统中找不到该项目对应的价格/套餐方案 (project_id: {project_id})")

    def register_user(self, plan_id, student_info):
        """执行最终的注册/开卡 POST 请求"""
        url = f"{self.BASE_URL}/api/trainmanager/register/projects"
        payload = {
            "planType": "0",
            "userList": [
                {
                    "name": student_info.get("name", ""),
                    "telephone": student_info.get("phone", ""),
                    "idCard": student_info.get("id_card", ""),
                    "work": student_info.get("company", ""),
                    "jobName": "企业职工", # 下拉框默认
                    "education": "",
                    "nation": "",
                    "note": "",
                    "perposition": "",
                    "title": "",
                    "personnel_type": "",
                    "initial_collection_date": "",
                    "apNote": ""
                }
            ],
            "planId": str(plan_id),
            "projectType": "0",
            "payState": "0"
        }
        logger.info(f"即将发送装配完毕的开卡 payload 至外部系统: {payload}")
        try:
            res = self.session.post(url, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            logger.info(f"外部系统开卡接口原始返回: {data}")
            if data.get("code") != 200:
                err_msg = data.get("message", "提交开卡申请到外部系统失败")
                logger.error(f"外部系统拒绝了开卡请求，原因: {err_msg}")
                raise JunruiServiceError(err_msg)
            
            success_msg = data.get("message", "外部系统开卡请求已成功受理")
            logger.info(f"开卡成功落地完毕，返回消息: {success_msg}")
            return success_msg
        except requests.RequestException as e:
            logger.error(f"注册开卡接口网络异常: {e}")
            raise JunruiServiceError("网络异常：开卡请求超时或被拒绝")

    def query_card_info(self, id_card):
        """
        通过身份证号查询君瑞系统中的学习卡信息。

        调用 /api/trainmanager/register/grid 接口，
        遍历结果用身份证号匹配，返回卡号和密码。

        返回:
            dict: {'card_id': '...', 'card_pwd': '...', 'state': '...'} 或 None
        """
        logger.info(f"查询君瑞学习卡信息: 身份证={id_card[:6]}****{id_card[-4:]}")
        url = f"{self.BASE_URL}/api/trainmanager/register/grid"

        # 查最近一年的记录，分页取前 100 条
        from datetime import datetime, timedelta
        begin = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        payload = {
            "beginTime": begin,
            "state": "0",
            "offset": 0,
            "limit": 100
        }

        try:
            res = self.session.post(url, json=payload, timeout=15)
            res.raise_for_status()
            data = res.json()
            if data.get("code") != 200:
                logger.warning(f"查询学习卡列表失败: {data.get('message')}")
                return None

            records = data.get("entity", [])
            for r in records:
                if r.get("id_card") == id_card:
                    card_info = {
                        "card_id": r.get("pay_card_id", ""),
                        "card_pwd": r.get("pay_card_pwd", ""),
                        "state": r.get("state", ""),
                        "junrui_id": r.get("id"),
                        "project_name": r.get("xmmc", ""),
                    }
                    logger.info(f"查询到学习卡: 卡号={card_info['card_id']} 状态={card_info['state']}")
                    return card_info

            logger.info(f"未在君瑞系统中查到该身份证的学习卡记录")
            return None
        except requests.RequestException as e:
            logger.error(f"查询学习卡接口异常: {e}")
            return None


def activate_card_for_student(student_dict):
    """
    提供给路由层的上层调用封装：
    从登录到完整流程开卡，返回外部系统的 message 提示。
    """
    student_id = student_dict.get("_id")
    job_cat = student_dict.get("job_category")
    exam_proj = student_dict.get("exam_project")
    
    logger.info(f"======== 开始执行外系统开卡流程 | 学员ID: {student_id} ========")

    service = JunruiService()
    try:
        service.login()
        cat_id = service.get_category_id(job_cat)
        proj_id = service.get_project_id(cat_id, exam_proj)
        plan_id = service.get_plan_id(proj_id, "50")

        student_info = {
            "name": student_dict.get("name"),
            "phone": student_dict.get("phone"),
            "id_card": student_dict.get("id_card"),
            "company": student_dict.get("company") or "暂无单位"
        }
        res_msg = service.register_user(plan_id, student_info)
        return {"success": True, "message": res_msg}

    except JunruiServiceError as e:
        logger.error(f"君瑞平台开卡失败(学员ID {student_dict.get('_id')}): {e}")
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.exception(f"君瑞平台开卡发生意外错误(学员ID {student_dict.get('_id')}): {e}")
        return {"success": False, "message": "跨系统对接未知错误，请查看后台日志"}


def query_card_for_student(student_dict):
    """
    单独查询学习卡信息（用于已开卡学员补查卡号）。
    """
    id_card = student_dict.get("id_card", "")
    if not id_card:
        return {"success": False, "message": "学员身份证号为空"}

    service = JunruiService()
    try:
        service.login()
        card_info = service.query_card_info(id_card)
        if card_info:
            return {"success": True, **card_info}
        return {"success": False, "message": "未在君瑞系统中查到该学员的学习卡信息"}
    except JunruiServiceError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.exception(f"查询学习卡异常: {e}")
        return {"success": False, "message": "查询异常，请查看后台日志"}

