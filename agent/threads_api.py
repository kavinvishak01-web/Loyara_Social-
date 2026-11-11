"""Minimal client for Meta's official Threads API (graph.threads.net)."""
from __future__ import annotations

import time
from typing import Dict, Optional

import requests

BASE = "https://graph.threads.net/v1.0"


class ThreadsError(RuntimeError):
    pass


class Threads:
    def __init__(self, token: str, user_id: str = "me"):
        self.token = token
        self.user_id = user_id or "me"

    def _req(self, method: str, path: str, **params) -> Dict:
        params["access_token"] = self.token
        r = requests.request(method, f"{BASE}/{path}", params=params, timeout=60)
        data = r.json() if r.content else {}
        if r.status_code >= 400 or "error" in data:
            msg = data.get("error", {}).get("message", r.text)
            raise ThreadsError(f"{method} {path} failed ({r.status_code}): {msg}")
        return data

    def _wait(self, container_id: str, timeout: int = 300) -> None:
        start = time.time()
        while time.time() - start < timeout:
            st = self._req("GET", container_id, fields="status,error_message")
            if st.get("status") == "FINISHED":
                return
            if st.get("status") in ("ERROR", "EXPIRED"):
                raise ThreadsError(f"container {container_id}: {st}")
            time.sleep(10)
        raise ThreadsError(f"container {container_id} not ready after {timeout}s")

    def _publish(self, params: Dict) -> str:
        try:
            c = self._req("POST", f"{self.user_id}/threads", **params)
        except ThreadsError:
            if "topic_tag" not in params:
                raise
            params = {k: v for k, v in params.items() if k != "topic_tag"}
            c = self._req("POST", f"{self.user_id}/threads", **params)
        self._wait(c["id"])
        return self._req("POST", f"{self.user_id}/threads_publish", creation_id=c["id"])["id"]

    def post_image(self, text: str, image_url: str, topic_tag: Optional[str] = None) -> str:
        params = {"media_type": "IMAGE", "image_url": image_url, "text": text}
        if topic_tag:
            params["topic_tag"] = topic_tag
        return self._publish(params)

    def reply(self, to_id: str, text: str) -> str:
        return self._publish({"media_type": "TEXT", "text": text, "reply_to_id": to_id})

    def permalink(self, media_id: str) -> str:
        return self._req("GET", media_id, fields="permalink").get("permalink", "")

    def insights(self, media_id: str) -> Dict[str, int]:
        data = self._req("GET", f"{media_id}/insights",
                         metric="views,likes,replies,reposts,quotes,shares")
        out = {}
        for m in data.get("data", []):
            vals = m.get("values") or [{}]
            out[m["name"]] = vals[0].get("value", m.get("total_value", {}).get("value", 0))
        return out

    @staticmethod
    def refresh(token: str) -> Dict:
        r = requests.get("https://graph.threads.net/refresh_access_token",
                         params={"grant_type": "th_refresh_token", "access_token": token}, timeout=30)
        data = r.json()
        if "access_token" not in data:
            raise ThreadsError(f"token refresh failed: {data}")
        return data
