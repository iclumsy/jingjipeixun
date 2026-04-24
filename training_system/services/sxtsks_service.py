"""
山西特种设备考试报名平台 (www.sxtsks.com) 自动化对接服务。

核心功能:
    - 自动登录（RSA 加密密码 + ddddocr 验证码识别）
    - 自动提交学员报名
    - 查询已提交的报名记录
    - 下载申请表 PDF

使用方式:
    client = SxtsksClient()
    client.login()
    result = client.submit_and_download(student_data, photo_path)
"""
import os
import io
import re
import time
import logging
import requests
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# ======================== 常量配置 ========================

BASE_URL = 'http://www.sxtsks.com'

# 登录凭证
LOGIN_ID_CARD = '130983198906195314'
LOGIN_PASSWORD = '53299009'

# RSA 公钥（从平台登录页 JS 提取）
RSA_PUBLIC_KEY = 'MFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAKoR8mX0rGKLqzcWmOzbfj64K8ZIgOdHnzkXSOVOZbFu/TJhZ7rFAN+eaGkl3C4buccQd/EjEsj9ir7ijT7h96MCAwEAAQ=='

# 阳泉市固定参数
JGDM = '140300111'       # 发证机构代码
JGLB = '9002'            # 机构类别
KSJGDM = '14030001'      # 考试机构代码
YZBM = '045000'          # 邮编
GZJL = '从事特种设备工作三个月以上。'  # 工作简历

# 学历映射：小程序值 → 平台代码
EDUCATION_MAP = {
    '初中': '0403',
    '中技': '0406',
    '中专': '0405',
    '中专或同等学历': '0405',
    '职高': '0407',
    '高中': '0408',
    '高中或同等学历': '0408',
    '高技': '0413',
    '大专': '0409',
    '专科或同等学历': '0409',
    '本科': '0410',
    '本科或同等学历': '0410',
    '硕士': '0411',
    '研究生及以上': '0411',
    '博士': '0412',
}

# 项目代号 → 平台 XMID 映射
PROJECT_CODE_TO_XMID = {
    'A':  '0195',   # 特种设备安全管理
    'G1': '0295',   # 工业锅炉司炉
    'G3': '0297',   # 锅炉水处理
    'R1': '0395',   # 快开门式压力容器操作
    'P':  '0495',   # 气瓶充装
    'Q1': '0791',   # 起重机指挥
    'Q2(限塔式起重机)':      '0793',
    'Q2(限门座式起重机)':    '0794',
    'Q2(限缆索式起重机)':    '0795',
    'Q2(限流动式起重机)':    '0796',
    'N1': '1095',   # 叉车司机
}

# 性别映射
GENDER_MAP = {
    '男': '1',
    '女': '2',
}

# 相关材料代码（根据 HAR 数据，固定勾选）
# 07101 = 身份证明, 07102 = 学历证明, 07103 = 体检报告
XGCL_DEFAULT = ['07101', '07102', '07103']

# 验证码最大重试次数
MAX_CAPTCHA_RETRIES = 5


def _rsa_encrypt(plaintext, public_key_b64=RSA_PUBLIC_KEY):
    """
    使用 RSA 公钥加密密码，与平台 JSEncrypt 行为一致。

    参数:
        plaintext: 明文密码
        public_key_b64: base64 编码的 DER 公钥

    返回:
        str: base64 编码的密文
    """
    try:
        from Crypto.PublicKey import RSA
        from Crypto.Cipher import PKCS1_v1_5
        import base64

        der_key = base64.b64decode(public_key_b64)
        rsa_key = RSA.import_key(der_key)
        cipher = PKCS1_v1_5.new(rsa_key)
        ciphertext = cipher.encrypt(plaintext.encode('utf-8'))
        return base64.b64encode(ciphertext).decode('utf-8')
    except ImportError:
        logger.warning('pycryptodome 未安装，尝试使用 rsa 库')
        try:
            import rsa as rsa_lib
            import base64
            der_key = base64.b64decode(public_key_b64)
            pub_key = rsa_lib.PublicKey.load_pkcs1_openssl_der(der_key)
            ciphertext = rsa_lib.encrypt(plaintext.encode('utf-8'), pub_key)
            return base64.b64encode(ciphertext).decode('utf-8')
        except ImportError:
            raise RuntimeError('需要安装 pycryptodome 或 rsa 库来进行 RSA 加密')


def _ocr_captcha(image_bytes):
    """
    使用 ddddocr 识别验证码图片。

    参数:
        image_bytes: 验证码图片的二进制内容

    返回:
        str: 识别出的验证码文本
    """
    try:
        import ddddocr
        ocr = ddddocr.DdddOcr(show_ad=False)
        result = ocr.classification(image_bytes)
        return result.strip()
    except ImportError:
        raise RuntimeError('ddddocr 未安装，请执行 pip install ddddocr')


class SxtsksClient:
    """
    报名平台 HTTP 客户端。

    使用 requests.Session 维持登录态（Cookie），
    提供登录、报名、查询、下载申请表等完整业务方法。
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Origin': 'http://www.sxtsks.com',
            'Referer': 'http://www.sxtsks.com/userLoginIndex.do',
            'Upgrade-Insecure-Requests': '1'
        })
        self.userid = None
        self.logged_in = False
        self._steps = []  # 步骤日志收集器

    def _log_step(self, step, status, detail='', resp=None):
        """记录一个操作步骤的详细日志。"""
        entry = {
            'step': step,
            'status': status,  # ok / fail / warning
            'detail': detail,
            'time': time.strftime('%H:%M:%S'),
        }
        if resp is not None:
            entry['http_status'] = resp.status_code
            entry['url'] = resp.url[:120] if resp.url else ''
            content_type = resp.headers.get('Content-Type', '')
            entry['content_type'] = content_type[:60]
            # 记录响应摘要（截断）
            if 'json' in content_type:
                entry['response'] = resp.text[:500]
            elif 'html' in content_type:
                entry['response_length'] = len(resp.text)
                # 从 HTML 中提取有用信息（仅提取包含 alert 包含特定错误时的关键词，避免误提取页面静态代码）
                import re as _re
                alerts = _re.findall(r'alert\(["\'](.*?不正确.*?|.*?不符合.*?|.*?已存在.*?|.*?失败.*?)["\']\)', resp.text[:3000])
                if alerts:
                    entry['alerts'] = alerts[:5]
            else:
                entry['response_length'] = len(resp.content)
        self._steps.append(entry)
        # 同时输出到 logger
        log_msg = f'[sxtsks] {step}: {status} - {detail}'
        
        from flask import has_app_context, current_app
        if has_app_context():
            app_logger = current_app.logger
        else:
            app_logger = logger
            
        if status == 'fail':
            app_logger.error(log_msg)
        elif status == 'warning':
            app_logger.warning(log_msg)
        else:
            app_logger.info(log_msg)

    def get_steps(self):
        """获取并清空步骤日志。"""
        steps = list(self._steps)
        self._steps.clear()
        return steps

    def login(self, id_card=LOGIN_ID_CARD, password=LOGIN_PASSWORD):
        """
        登录报名平台。

        流程: 获取验证码图片 → OCR 识别 → RSA 加密密码 → 提交登录
        验证码识别失败时自动重试。

        返回:
            dict: {'success': True/False, 'message': str, 'attempts': int}
        """
        self._log_step('登录-加密密码', 'ok', f'RSA 加密完成，身份证={id_card[:6]}***')
        encrypted_pwd = _rsa_encrypt(password)

        for attempt in range(1, MAX_CAPTCHA_RETRIES + 1):
            try:
                # 1. 获取验证码图片
                captcha_url = f'{BASE_URL}/getAuthImage.do?date={int(time.time() * 1000)}'
                captcha_resp = self.session.get(captcha_url, timeout=10)
                if captcha_resp.status_code != 200:
                    self._log_step(f'登录-验证码(第{attempt}次)', 'fail', f'HTTP {captcha_resp.status_code}', captcha_resp)
                    continue
                self._log_step(f'登录-验证码(第{attempt}次)', 'ok', f'图片 {len(captcha_resp.content)} 字节')

                # 2. OCR 识别验证码
                captcha_text = _ocr_captcha(captcha_resp.content)
                self._log_step(f'登录-OCR(第{attempt}次)', 'ok', f'识别结果: {captcha_text}')

                if not captcha_text or len(captcha_text) < 3:
                    self._log_step(f'登录-OCR(第{attempt}次)', 'warning', f'结果太短 "{captcha_text}"，重试')
                    continue

                # 3. 提交登录
                login_resp = self.session.post(
                    f'{BASE_URL}/loginByIdCard.do',
                    data={
                        'idCard': id_card,
                        'password': encrypted_pwd,
                        'validCode': captcha_text,
                    },
                    timeout=15,
                    allow_redirects=True,
                )

                # 判断登录结果 - 接口返回 JSON: {"text":"登录成功！","code":1}
                try:
                    login_data = login_resp.json()
                    if login_data.get('code') != 1:
                        self._log_step(f'登录-提交(第{attempt}次)', 'fail', f'平台拒绝: {login_data.get("text", "")}', login_resp)
                        continue
                except (ValueError, AttributeError):
                    # 非 JSON 响应，检查 URL 是否重定向回登录页
                    if 'turnToUserLogin' in login_resp.url:
                        self._log_step(f'登录-提交(第{attempt}次)', 'fail', '重定向回登录页，验证码可能错误', login_resp)
                        continue

                self.logged_in = True
                self._log_step(f'登录-提交(第{attempt}次)', 'ok', '登录成功', login_resp)

                # 登录成功后访问主页提取 userid
                try:
                    home_resp = self.session.get(f'{BASE_URL}/turnToUserLogin.do', timeout=10)
                    userid_match = re.search(r'userid[=:"\s]*(\d+)', home_resp.text)
                    if userid_match:
                        self.userid = userid_match.group(1)
                        self._log_step('登录-获取userid', 'ok', f'userid={self.userid}')
                    else:
                        # 从 URL 参数中再找
                        userid_match2 = re.search(r'userid=(\d+)', home_resp.url)
                        if userid_match2:
                            self.userid = userid_match2.group(1)
                            self._log_step('登录-获取userid', 'ok', f'userid={self.userid}(从URL)')
                        else:
                            self._log_step('登录-获取userid', 'warning', f'未从主页提取到userid，页面长度={len(home_resp.text)}')
                except Exception as ue:
                    self._log_step('登录-获取userid', 'warning', str(ue))

                return {
                    'success': True,
                    'message': f'登录成功（第{attempt}次尝试）',
                    'attempts': attempt,
                    'userid': self.userid,
                }

            except Exception as e:
                self._log_step(f'登录-异常(第{attempt}次)', 'fail', str(e))
                continue

        self._log_step('登录', 'fail', f'已重试 {MAX_CAPTCHA_RETRIES} 次均失败')
        return {
            'success': False,
            'message': f'登录失败，已重试 {MAX_CAPTCHA_RETRIES} 次',
            'attempts': MAX_CAPTCHA_RETRIES,
        }

    def _ensure_login(self):
        """确保已登录，未登录则自动登录。"""
        if not self.logged_in:
            result = self.login()
            if not result['success']:
                raise RuntimeError(f'自动登录失败: {result["message"]}')

    def upload_photo(self, photo_path, zyxm_id):
        """
        上传证件照到报名平台。

        参数:
            photo_path: 本地照片路径
            zyxm_id: 作业项目 ID

        返回:
            str: 平台返回的临时照片路径（如 tmp/xxx.jpg）
        """
        self._ensure_login()

        with open(photo_path, 'rb') as f:
            photo_data = f.read()

        self._log_step('上传照片', 'ok', f'照片大小 {len(photo_data)} 字节，项目 {zyxm_id}')
        resp = self.session.post(
            f'{BASE_URL}/uploadksimg.do',
            params={
                'suffix': 'jpg',
                'filename': 'files',
                'zyxm': zyxm_id,
            },
            files={
                'files': ('photo.jpg', photo_data, 'image/jpeg'),
            },
            data={
                'bmid': '',
                'sblsh': '',
                'jgdm': JGDM,
            },
            timeout=30,
        )

        # 响应格式: <script>window.parent._upload_callbacks('tmp/xxx.jpg?dateXXX','1');</script>
        match = re.search(r"_upload_callbacks\(['\"]([^'\"]+)['\"]", resp.text)
        if match:
            tmp_path = match.group(1)
            self._log_step('上传照片-结果', 'ok', f'平台路径: {tmp_path}', resp)
            return tmp_path
        else:
            self._log_step('上传照片-结果', 'fail', f'响应: {resp.text[:300]}', resp)
            raise RuntimeError(f'照片上传失败，响应: {resp.text[:200]}')

    def _get_form_token(self, sfzh, zyxm_id):
        """
        获取报名表单页面中的 bmVerriToken 防重 token。

        参数:
            sfzh: 学员身份证号
            zyxm_id: 作业项目 XMID

        返回:
            str: bmVerriToken 值
        """
        # 先保存身份证
        r0 = self.session.post(
            f'{BASE_URL}/saveDwbmSfzh.do',
            data={'sfzh': sfzh},
            timeout=10,
        )
        self._log_step('保存身份证到会话', 'ok', f'sfzh={sfzh}', r0)

        # 打开报名表单页面
        resp = self.session.get(
            f'{BASE_URL}/dwbm_kzbm.do',
            params={
                'jgdm': JGDM,
                'jglb': JGLB,
                'sfzh': sfzh,
                'processStatus': 'undefined',
                'zyxm': zyxm_id,
                'userid': self.userid or '',
                'ksjg_dm': KSJGDM,
            },
            timeout=15,
        )

        # 提取 bmVerriToken（多种可能的 HTML 模式）
        token = ''
        patterns = [
            r'name="bmVerriToken"[^>]*value="([^"]+)"',   # <input name="bmVerriToken" value="xxx">
            r'value="([^"]+)"[^>]*name="bmVerriToken"',   # <input value="xxx" name="bmVerriToken">
            r'bmVerriToken["\s]+value="([^"]+)"',          # 原有模式
            r'bmVerriToken["\']?\s*[:,=]\s*["\']([^"\']+)', # JS 变量赋值
            r'id="bmVerriToken"[^>]*value="([^"]+)"',      # id 模式
        ]
        for pat in patterns:
            m = re.search(pat, resp.text)
            if m:
                token = m.group(1)
                self._log_step('获取表单token', 'ok', f'bmVerriToken={token[:20]}... (模式: {pat[:30]})', resp)
                break
        if not token:
            self._log_step('获取表单token', 'warning', f'未找到 bmVerriToken，页面长度={len(resp.text)}', resp)
        return token

    def _get_captcha_code(self):
        """获取并识别新的验证码。"""
        captcha_resp = self.session.get(
            f'{BASE_URL}/getAuthImage.do?date={int(time.time() * 1000)}',
            timeout=10,
        )
        return _ocr_captcha(captcha_resp.content)

    def _upload_attachment(self, code, photo_data, zyxm_id):
        """上传单独的附件（身份证明等）"""
        att_filename = f'tj{code}'
        self._log_step(f'上传附件-{code}', 'ok', f'准备上传, ID={att_filename}')
        try:
            att_resp = self.session.post(
                f'{BASE_URL}/uploadksimg.do',
                params={'suffix': 'jpg', 'filename': att_filename, 'zyxm': str(zyxm_id)},
                files={att_filename: ('attachment.jpg', photo_data, 'image/jpeg')},
                timeout=15,
            )
            # 解析响应: <script>window.parent._upload_callbacks('tmp/xxx.jpg','1');</script>
            import re
            match = re.search(r"_upload_callbacks\(['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", att_resp.text)
            status_code = match.group(2) if match else ''
            
            if match and status_code == '1':
                self._log_step(f'上传附件结果-{code}', 'ok', '成功', att_resp)
            else:
                self._log_step(f'上传附件结果-{code}', 'fail', f'状态: {status_code} 响应: {att_resp.text[:100]}', att_resp)
        except Exception as e:
            self._log_step(f'上传附件结果-{code}', 'warning', f'异常: {str(e)}')

    def _run_pre_checks(self, sfzh, zyxm_id):
        """
        执行提交前的多步校验（模拟前端 JS 行为）。

        返回:
            dict: 校验结果，包含各步骤响应
        """
        results = {}
        checks = [
            ('校验学历', lambda: self.session.get(
                f'{BASE_URL}/dwbm_validateWhcd.do',
                params={'zyxm': zyxm_id, 'whcd': '0405', '_': int(time.time() * 1000)}, timeout=10)),
            ('检查证书', lambda: self.session.post(
                f'{BASE_URL}/isKsCertExists.do',
                params={'web_ksjgdm': JGDM},
                data={'zyzl': '', 'zyxm': zyxm_id, 'sfzh': sfzh}, timeout=10)),
            ('验证身份证', lambda: self.session.post(
                f'{BASE_URL}/verifyDwBmIdCard.do',
                data={'idCard': sfzh, 'jgdm': JGDM}, timeout=10)),
            ('检查可否报名', lambda: self.session.post(
                f'{BASE_URL}/wbisCanApply.do',
                data={'bmlb': '0', 'jgdm': JGDM, 'sfzh': sfzh, 'zyzl': '', 'zyxm': zyxm_id}, timeout=10)),
            ('检查考试状态', lambda: self.session.post(
                f'{BASE_URL}/isExamDoing.do',
                data={'bmlb': '0', 'jgdm': JGDM, 'sfzh': sfzh, 'zyzl': '', 'zyxm': zyxm_id}, timeout=10)),
        ]
        for name, call in checks:
            try:
                r = call()
                resp_summary = r.text[:200] if r.text else '(empty)'
                self._log_step(f'预校验-{name}', 'ok', resp_summary, r)
                results[name] = r.text
            except Exception as e:
                self._log_step(f'预校验-{name}', 'warning', str(e))

        # 验证码校验
        try:
            ver_code = self._get_captcha_code()
            r = self.session.post(
                f'{BASE_URL}/checkVerCode.do',
                data={'verCode': ver_code},
                timeout=10,
            )
            results['checkVerCode'] = r.text
            results['verCode'] = ver_code
            try:
                cv_json = r.json()
                if cv_json.get('code') == 0:
                    results['bmVerriToken'] = cv_json.get('text', '')
            except Exception:
                pass
        except Exception as e:
            logger.warning(f'验证码校验异常: {e}')
            results['verCode'] = ''
            results['bmVerriToken'] = ''

        return results

    def submit_registration(self, student, photo_path):
        """
        提交单个学员的报名信息。

        参数:
            student: 学员数据字典，需包含:
                name, gender, id_card, education, phone, company,
                company_address, project_code
            photo_path: 证件照本地路径

        返回:
            dict: {'success': True/False, 'message': str, 'bmid': str}
        """
        self._ensure_login()

        sfzh = student['id_card']
        
        # [DEBUG] 拦截真实身份证并每次生成一个随机的 18 位测试身份证
        import random
        old_sfzh = sfzh
        # 生成一个基础的山西阳泉随机身份证
        random_sfzh = f"14030219{random.randint(70,99)}{random.randint(1,12):02d}{random.randint(1,28):02d}{random.randint(1000,9999)}"
        sfzh = random_sfzh
        self._log_step('测试模式', 'warning', f'已将报考身份证 {old_sfzh} 强制替换为测试身份证 {sfzh}')
        
        project_code = student.get('project_code', '')
        zyxm_id = PROJECT_CODE_TO_XMID.get(project_code)
        if not zyxm_id:
            return {'success': False, 'message': f'未知的项目代号: {project_code}'}

        gender_code = GENDER_MAP.get(student.get('gender', ''), '1')
        education_code = EDUCATION_MAP.get(student.get('education', ''), '0405')
        company = student.get('company', '')
        company_address = student.get('company_address', '')

        try:
            # 1. 上传照片
            self._log_step('报名开始', 'ok', f'{student["name"]}（{sfzh}）项目={project_code} → XMID={zyxm_id}')
            self.upload_photo(photo_path, zyxm_id)

            # 获取表单 token
            token = self._get_form_token(sfzh, zyxm_id)

            # 3. 执行预校验
            check_results = self._run_pre_checks(sfzh, zyxm_id)
            ver_code = check_results.get('verCode', '')
            
            if not token:
                token = check_results.get('bmVerriToken', '')
            
            if not ver_code:
                ver_code = self._get_captcha_code()

            # 新增: 提交表单前上传证明材料 (07101 = 身份证明, 07102 = 学历证明, 07103 = 体检报告)
            # 平台上点击"添加附件"就是发此类请求
            with open(photo_path, 'rb') as f:
                photo_data = f.read()

            for code in XGCL_DEFAULT:
                self._upload_attachment(code, photo_data, zyxm_id)

            # 4. 检查是否需要配合机构必选
            try:
                r = self.session.post(
                    f'{BASE_URL}/queryKsjgIsMust.do',
                    data={'jgdm': JGDM},
                    timeout=10,
                )
            except Exception:
                pass

            # 5. 构建并提交表单
            self._log_step('构建表单', 'ok', f'token={token[:15]}... verCode={ver_code} 学历={education_code} 性别={gender_code}')

            # 构建 multipart 表单数据
            form_fields = {
                'bmid': '',
                'sblsh': '',
                'jgdm': JGDM,
                'jglb': JGLB,
                'web_ksjgdm': JGDM,
                'bmjgdm': JGDM,
                'flag': '',
                'bmlb': '',
                'bmVerriToken': token,
                'tzsbzl': '',
                'lzfs': '',
                'sjrxm': '',
                'sjrlxdh': '',
                'sjrxxdz': '',
                'sjryzbm': '',
                'zwwbm': '',
                'business_code': '',
                'v_sfzh': '',
                'processStatus': '',
                'userid': self.userid or '',
                'v_lxdh': '',
                'phoneIsReq': '',
                'siteX': '',
                'pxjgdm': '',
                'ksjgdm': KSJGDM,
                'sqrxm': student['name'],
                'xb': gender_code,
                'zjlx': '1',
                'sfzh': sfzh,
                'whcd': education_code,
                'yrdw': company,
                'dwdz': company_address,
                'txdz': company_address,
                'yzbm': YZBM,
                'lxdh': student.get('phone', ''),
                'zyxm': zyxm_id,
                'zyzl': '',
                'zyxmcode': zyxm_id,
                'dwszdq': '',
                'dwszqx': '',
                'gzjl': GZJL,
                'yrdwyj': '',
                'yrdwrq': time.strftime('%Y-%m-%d'),
                'sqrqzrq': time.strftime('%Y-%m-%d'),
                'verCode': ver_code,
                'xgclType': '071',
            }

            # 构建 multipart 请求
            # 注意 xgcl 需要多个同名字段
            files_list = []
            for key, value in form_fields.items():
                files_list.append((key, (None, value)))

            # 多个 xgcl 字段
            for code in XGCL_DEFAULT:
                files_list.append(('xgcl', (None, code)))

            # 照片文件
            files_list.append(('files', ('photo.jpg', photo_data, 'image/jpeg')))

            # 发送请求，加上 X-Requested-With 以防止被 Struts 当作普通跳转而返回表单页
            resp = self.session.post(
                f'{BASE_URL}/dwbm_savekzbmb.do',
                files=files_list,
                headers={'X-Requested-With': 'XMLHttpRequest'},
                timeout=30,
            )

            # 判断是否成功
            self._log_step('提交表单-响应', 'ok', f'HTTP {resp.status_code}, 长度={len(resp.text)}', resp)
            if resp.status_code == 200:
                resp_text = resp.text.strip()
                if '保存并上报成功' in resp_text:
                    # 响应格式: "保存并上报成功,12345"
                    parts = resp_text.split(',')
                    bmid = parts[1] if len(parts) > 1 else ''
                    self._log_step('提交表单-结果', 'ok', f'报名成功 bmid={bmid}')
                    return {'success': True, 'message': '报名提交成功', 'bmid': bmid}
                elif '验证码' in resp_text and '不正确' in resp_text:
                    self._log_step('提交表单-结果', 'fail', '验证码错误')
                    return {'success': False, 'message': '验证码错误'}
                elif '已存在' in resp_text:
                    self._log_step('提交表单-结果', 'fail', resp_text)
                    return {'success': False, 'message': f'报名失败: {resp_text}'}
                else:
                    self._log_step('提交表单-结果', 'warning', f'未知响应: {resp_text[:100]}')
                    return {'success': False, 'message': f'未知响应: {resp_text}'}
            else:
                self._log_step('提交表单-结果', 'fail', f'HTTP {resp.status_code}')
                return {'success': False, 'message': f'HTTP 错误: {resp.status_code}'}

        except Exception as e:
            self._log_step('提交表单-异常', 'fail', str(e))
            return {'success': False, 'message': f'报名异常: {str(e)}'}

    def query_registrations(self, sfzh=None):
        """
        查询已提交的报名记录。

        参数:
            sfzh: 按身份证查询，为空则查全部

        返回:
            list[dict]: 报名记录列表
        """
        self._ensure_login()

        resp = self.session.post(
            f'{BASE_URL}/dwbm_queryKsZtInfo.do',
            params={
                'sfzh': LOGIN_ID_CARD,
                'userid': self.userid or '',
            },
            data={
                'page': '1',
                'rp': '100',
                'sortname': 'undefined',
                'sortorder': 'undefined',
                'query': '',
                'qtype': '',
                'params': '',
                'bmlb': '',
                'zyzltwo': '',
                'zyxmtwo': '',
            },
            headers={'X-Requested-With': 'XMLHttpRequest'},
            timeout=15,
        )

        if resp.status_code != 200:
            logger.error(f'查询报名列表失败: HTTP {resp.status_code}')
            return []

        try:
            data = resp.json()
            rows = data.get('rows', [])
            result = []
            for row in rows:
                # 如果指定了 sfzh，只返回匹配的
                if sfzh and row.get('SFZH') != sfzh:
                    continue
                result.append({
                    'bmid': row.get('BMID'),
                    'name': row.get('SQRXM'),
                    'id_card': row.get('SFZH'),
                    'project': row.get('ZYXM'),
                    'project_code': row.get('ZYXM_DM'),
                    'status': row.get('FLAG'),
                    'apply_date': row.get('SQRQ'),
                    'exam_org': row.get('KSJG_MC'),
                    'edit_url': row.get('CZ'),
                })
            return result
        except Exception as e:
            logger.error(f'解析报名列表失败: {e}')
            return []

    def download_application_form(self, bmid):
        """
        下载申请表 PDF/HTML。

        参数:
            bmid: 报名 ID

        返回:
            tuple: (content_bytes, content_type, filename)
        """
        self._ensure_login()

        resp = self.session.get(
            f'{BASE_URL}/dwbm_printBzSqb.do',
            params={'bmid': bmid},
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(f'下载申请表失败: HTTP {resp.status_code}')

        content_type = resp.headers.get('Content-Type', 'text/html')
        filename = f'申请表-{bmid}'

        if 'pdf' in content_type.lower():
            filename += '.pdf'
        elif 'html' in content_type.lower():
            filename += '.html'
        else:
            filename += '.pdf'

        return resp.content, content_type, filename

    def submit_and_download(self, student, photo_path, output_dir=None):
        """
        一键完成：报名 → 查询 → 下载申请表。

        参数:
            student: 学员数据字典
            photo_path: 证件照路径
            output_dir: 申请表保存目录，为空则只返回内容

        返回:
            dict: {
                'success': bool,
                'message': str,
                'bmid': str,
                'form_path': str (如果指定了 output_dir),
                'form_content': bytes,
            }
        """
        # 1. 提交报名
        submit_result = self.submit_registration(student, photo_path)
        if not submit_result.get('success'):
            submit_result['steps'] = self.get_steps()
            return submit_result

        # 2. 查询报名获取 bmid
        bmid = submit_result.get('bmid')
        if not bmid:
            time.sleep(2)  # 等待平台处理
            registrations = self.query_registrations(sfzh=student['id_card'])
            for reg in registrations:
                if reg['id_card'] == student['id_card']:
                    bmid = str(reg['bmid'])
                    self._log_step('查询报名', 'ok', f'找到 bmid={bmid}')
                    break

        if not bmid:
            self._log_step('查询报名', 'warning', '未找到 bmid')
            result = {
                'success': True,
                'message': '报名已提交但未找到报名 ID，请手动查询',
                'bmid': '',
            }
            result['steps'] = self.get_steps()
            return result

        # 3. 下载申请表
        try:
            content, content_type, filename = self.download_application_form(bmid)
            self._log_step('下载申请表', 'ok', f'bmid={bmid}, 文件={filename}, 大小={len(content)} 字节')
            result = {
                'success': True,
                'message': '报名成功并已下载申请表',
                'bmid': bmid,
                'form_content': content,
                'form_filename': filename,
            }

            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
                form_path = os.path.join(output_dir, filename)
                with open(form_path, 'wb') as f:
                    f.write(content)
                result['form_path'] = form_path
                self._log_step('保存申请表', 'ok', form_path)

            result['steps'] = self.get_steps()
            return result

        except Exception as e:
            self._log_step('下载申请表', 'fail', str(e))
            result = {
                'success': True,
                'message': f'报名成功但下载申请表失败: {e}',
                'bmid': bmid,
            }
            result['steps'] = self.get_steps()
            return result
