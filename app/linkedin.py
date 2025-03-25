import requests
import json

LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
LINKEDIN_POST_URL = "https://api.linkedin.com/v2/ugcPosts"

def get_user_info(access_token):
    """
    Retrieve the LinkedIn user info using the provided access token.
    Returns the user's LinkedIn ID (sub), name, and email.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(LINKEDIN_USERINFO_URL, headers=headers)

    if response.status_code == 200:
        data = response.json()
        return {
            "id": data.get("sub"),
            "name": data.get("name"),
            "email": data.get("email"),
            "profile_pic": data.get("picture")
        }
    else:
        raise Exception(f"Failed to fetch user info: {response.text}")

def post_to_linkedin(access_token, user_id, text):
    """
    Post a text-based update to LinkedIn.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "X-Restli-Protocol-Version": "2.0.0"
    }

    payload = {
        "author": f"urn:li:person:{user_id}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": text},
                "shareMediaCategory": "NONE"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }

    response = requests.post(LINKEDIN_POST_URL, headers=headers, data=json.dumps(payload))

    if response.status_code in (201, 200):
        return response.json()
    else:
        raise Exception(f"Failed to post: {response.text}")
