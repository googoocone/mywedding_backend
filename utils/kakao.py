import requests

def get_kakao_user(kakao_access_token:str) :
    token = kakao_access_token
    headers = {
        "Authorization" : f"Bearer {token}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }

    response = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers)

    if response.status_code != 200:
        raise Exception('카카오톡 유저 정보 확인 실패')
    
    return response.json()