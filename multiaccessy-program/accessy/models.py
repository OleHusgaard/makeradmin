from dataclasses import dataclass
from logging import getLogger
import os
import threading
import uuid
import warnings

import requests


logger = getLogger("accessy")
ACCESSY_URL = os.environ.get("ACCESSY_URL", "https://api.accessy.se")
CLIENT_ID = os.environ.get("ACCESSY_CLIENT_ID")
CLIENT_SECRET = os.environ.get("ACCESSY_CLIENT_SECRET")
ACCESSY_SESSION_TOKEN = os.environ.get("ACCESSY_SESSION_TOKEN", None)


def check_response_error(response: requests.Response, msg: str = None):
    if not response.ok:
        msg_str = f"\n\tMessage: {msg}" if msg is not None else ""
        logger.error(f"Got an error in the response. {response.status_code=}{msg_str}")
        raise RuntimeError(msg)


@dataclass
class AccessySession:
    SESSION_TOKEN: uuid

    @classmethod
    def create_session(cls, client_id: str, client_secret: str) -> "AccessySession":
        if not isinstance(client_id, str) or not isinstance(client_secret, str):
            raise TypeError("client_id and client_secret must be strings")

        response = requests.post(ACCESSY_URL + "/auth/oauth/token", 
            json={"audience": "https://api.accessy.se", "grant_type": "client_credentials", "client_id": client_id, "client_secret": client_secret},
            headers={"Content-Type": "application/json"}
        )
        if not response.ok:
            return None
        return cls(response.json()["access_token"])
    
    def __post_init__(self):
        self.organization_id = self._get_organization()

    def _get_organization(self) -> str:
        response = requests.get(ACCESSY_URL + "/asset/user/organization-membership",
            headers={"Authorization": f"Bearer {self.SESSION_TOKEN}"})
        # [{"id":<uuid>,"userId":<uuid>,"organizationId":<uuid>,"roles":[<roles>]}]

        check_response_error(response, "Get organization")

        data = response.json()
        if len(data) > 1:
            warnings.warn("API key has several memberships. This is probably an error...", RuntimeWarning)
        elif len(data) == 0:
            raise ValueError("The API key does not have a corresponding organization membership")

        return data[0]["organizationId"]

    def get_users(self) -> list[dict]:
        response = requests.get(ACCESSY_URL + f"/asset/admin/organization/{self.organization_id}/user",
            headers={"Authorization": f"Bearer {self.SESSION_TOKEN}"})

        check_response_error(response, "Get users")
        data = response.json()
        # {"items":[{"id":<uuid>,"msisdn":"+46...","firstName":str,"lastName":str}, ...],"totalItems":6,"pageSize":25,"pageNumber":0,"totalPages":1}

        page_number = data["pageNumber"]
        total_pages = data["totalPages"]
        items = data["items"]
        if page_number + 1 > total_pages:  # TODO: How to get more pages?
            logger.error(f"Did not get all of the users...")
        
        return items

    def get_membership(self, user_id: str) -> str:
        response = requests.get(ACCESSY_URL + f"/asset/admin/user/{user_id}/organization/{self.organization_id}/membership",
            headers={"Authorization": f"Bearer {self.SESSION_TOKEN}"})

        check_response_error(response, "Get membership")
        data = response.json()
        return data["id"]


@dataclass
class AccessyMember:
    membership_id: uuid
    user_id: uuid
    phone_number: str

    @classmethod
    def get_all(cls, session: AccessySession) -> list["AccessyMember"]:
        user_list = session.get_users()

        def get_membership(user: "AccessyMember", user_id: str):
            user.membership_id = session.get_membership(user_id)

        accessy_users = []
        threads = []
        for user in user_list:
            # API key does not have phone number
            phone_number = user.get("msisdn", None)
            if phone_number is None:
                continue

            user_id = user["id"]

            # Create user without membership, then update in-place in parallel
            accessy_user = cls(None, user_id, phone_number)
            accessy_users.append(accessy_user)
            _thread = threading.Thread(target=get_membership, args=(accessy_user, user_id), daemon=True)
            _thread.start()
            threads.append(_thread)

        for thread in threads:
            thread.join()

        return accessy_users


def main():
    session = None
    # Convenience if a session token is already issued
    if ACCESSY_SESSION_TOKEN is not None:
        try:
            session = AccessySession(ACCESSY_SESSION_TOKEN)
        except:
            pass
    
    # Get a new session token
    if session is None:
        session = AccessySession.create_session(CLIENT_ID, CLIENT_SECRET)
    print("session:", session)
    users = AccessyMember.get_all(session)
    print("users:", users)


if __name__ == "__main__":
    main()