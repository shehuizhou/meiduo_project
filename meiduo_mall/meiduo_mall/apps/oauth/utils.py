from itsdangerous import TimedJSONWebSignatureSerializer as Serializer,BadData
from django.conf import settings
def generate_openid_signature(openid):
    serializer = Serializer(secret_key=settings.SECRET_KEY,expires_in=600)
    data = {'openid':openid}
    openid_sign = serializer.dumps(data)
    return openid_sign.decode()

def check_openid_sign(openid_sign):
    serializer = Serializer(secret_key=settings.SECRET_KEY,expires_in=600)
    try:
        data = serializer.loads(openid_sign)
    except BadData:
        return None
    else:
        return data.get('openid')