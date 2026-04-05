import json
import os
import tencentcloud
from tencentcloud.common import credential
from tencentcloud.sts.v20180813 import sts_client, models
from dotenv import load_dotenv

load_dotenv()

secret_id = os.getenv('COS_SECRET_ID', '')
secret_key = os.getenv('COS_SECRET_KEY', '')
bucket = os.getenv('COS_BUCKET', '')
region = os.getenv('COS_REGION', '')

appid = bucket.split('-')[-1] if '-' in bucket else '*'

cred = credential.Credential(secret_id, secret_key)
client = sts_client.StsClient(cred, region)

req = models.GetFederationTokenRequest()
req.Name = "cos_direct_upload"
policy = {
    "version": "2.0",
    "statement": [
        {
            "action": [
                "name/cos:PutObject",
                "name/cos:PostObject"
            ],
            "effect": "allow",
            "resource": [
                f"qcs::cos:{region}:uid/{appid}:{bucket}/students/tmp/*"
            ]
        }
    ]
}
req.Policy = json.dumps(policy)
req.DurationSeconds = 1800

try:
    resp = client.GetFederationToken(req)
    print(resp.to_json_string(indent=2))
except Exception as e:
    print(e)
