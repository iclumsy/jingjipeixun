import json
import os
from flask import current_app
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.sts.v20180813 import sts_client, models

def get_cos_sts_token():
    """
    获取直传 COS 的临时凭证（STS Token）。
    该凭证仅允许上传到当前桶的 students/tmp/* 目录。
    """
    secret_id = os.getenv('COS_SECRET_ID', '')
    secret_key = os.getenv('COS_SECRET_KEY', '')
    bucket = os.getenv('COS_BUCKET', '')
    region = os.getenv('COS_REGION', '')

    if not all([secret_id, secret_key, region, bucket]):
        raise RuntimeError("COS 配置不完整，无法生成临时凭证")

    # 从 bucket 名称提取 appid（格式形如 examplebucket-1250000000）
    appid = bucket.split('-')[-1] if '-' in bucket else '*'

    cred = credential.Credential(secret_id, secret_key)
    
    httpProfile = HttpProfile()
    # 强制走内网端点可以通过特定配置，但默认公网也可
    httpProfile.endpoint = "sts.tencentcloudapi.com"

    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile

    client = sts_client.StsClient(cred, region, clientProfile)

    req = models.GetFederationTokenRequest()
    req.Name = "miniprogram_upload"
    
    # 构造仅允许 PutObject 和 PostObject 的 Policy
    policy = {
        "version": "2.0",
        "statement": [
            {
                "action": [
                    "name/cos:PutObject",
                    "name/cos:PostObject",
                    "name/cos:InitiateMultipartUpload",
                    "name/cos:ListMultipartUploads",
                    "name/cos:ListParts",
                    "name/cos:UploadPart",
                    "name/cos:CompleteMultipartUpload"
                ],
                "effect": "allow",
                "resource": [
                    f"qcs::cos:{region}:uid/{appid}:{bucket}/students/tmp/*"
                ]
            }
        ]
    }
    
    req.Policy = json.dumps(policy)
    # 设置过期时间 1800 秒（半小时）
    req.DurationSeconds = 1800

    try:
        import time
        resp = client.GetFederationToken(req)
        # 转换为字典返回
        return {
            "TmpSecretId": resp.Credentials.TmpSecretId,
            "TmpSecretKey": resp.Credentials.TmpSecretKey,
            "Token": resp.Credentials.Token,
            "StartTime": int(time.time()),
            "ExpiredTime": resp.ExpiredTime,
            "Bucket": bucket,
            "Region": region
        }
    except Exception as e:
        current_app.logger.error(f"Failed to generate STS Token: {str(e)}")
        raise RuntimeError(f"生成上传凭证失败: {str(e)}")
