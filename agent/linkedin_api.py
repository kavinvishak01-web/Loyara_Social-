"""Minimal LinkedIn client: image upload, post, first comment (personal profile, w_member_social)."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote

import requests

BASE = "https://api.linkedin.com/rest"


class LinkedInError(RuntimeError):
    pass


def escape_commentary(text: str) -> str:
    """LinkedIn's 'little text' format treats these as markup; unescaped they truncate the post."""
    escaped = re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", text)
    # turn #Word back into a real, clickable LinkedIn hashtag
    return re.sub(r"\\#(\w+)", r"{hashtag|\\#|\1}", escaped)


class LinkedIn:
    def __init__(self, token: str, author: str, version: str):
        self.author = author  # urn:li:person:XXXX
        self.h = {"Authorization": f"Bearer {token}", "LinkedIn-Version": version,
                  "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}

    def _check(self, r: requests.Response, what: str) -> None:
        if r.status_code >= 400:
            raise LinkedInError(f"{what} failed ({r.status_code}): {r.text[:300]}")

    def upload_image(self, path: Path) -> str:
        r = requests.post(f"{BASE}/images?action=initializeUpload", headers=self.h, timeout=60,
                          json={"initializeUploadRequest": {"owner": self.author}})
        self._check(r, "image init")
        v = r.json()["value"]
        up = requests.put(v["uploadUrl"], data=path.read_bytes(), timeout=120,
                          headers={"Authorization": self.h["Authorization"]})
        self._check(up, "image upload")
        return v["image"]

    def post(self, text: str, image_urn: str, alt: str) -> str:
        body = {
            "author": self.author,
            "commentary": escape_commentary(text),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": {"media": {"id": image_urn, "altText": alt[:300]}},
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        r = requests.post(f"{BASE}/posts", headers=self.h, json=body, timeout=60)
        self._check(r, "post")
        return r.headers.get("x-restli-id", "")

    def comment(self, post_urn: str, text: str) -> None:
        r = requests.post(f"{BASE}/socialActions/{quote(post_urn, safe='')}/comments", headers=self.h,
                          json={"actor": self.author, "object": post_urn, "message": {"text": text}},
                          timeout=60)
        self._check(r, "comment")
