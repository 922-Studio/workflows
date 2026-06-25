# coding: utf-8

"""API client module - httpx implementation replacing generated stubs."""

import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class ApiClient:
    """HTTP API client that actually makes requests via httpx.

    Replaces the generated stub client with real HTTP calls.
    """

    def __init__(self, configuration=None, header_name=None, header_value=None, cookie=None) -> None:
        from openapi_client.configuration import Configuration
        if configuration is None:
            configuration = Configuration.get_default()
        self.configuration = configuration
        self.default_headers = {"Content-Type": "application/json"}
        if header_name:
            self.default_headers[header_name] = header_value
        self.cookie = cookie
        self._client = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = dict(self.default_headers)
            if self.configuration.access_token:
                headers["Authorization"] = f"Bearer {self.configuration.access_token}"
            self._client = httpx.Client(
                follow_redirects=True,
                base_url=self.configuration.host,
                headers=headers,
                timeout=30.0,
                verify=self.configuration.verify_ssl,
            )
        return self._client

    def call_api(self, resource_path: str, method: str, path_params: dict = None,
                 query_params: dict = None, body: Any = None, **kwargs) -> Any:
        """Make the HTTP request and return parsed JSON response."""
        client = self._get_client()
        url = resource_path
        if path_params:
            for key, value in path_params.items():
                url = url.replace(f"{{{key}}}", str(value))
        params = {k: v for k, v in (query_params or {}).items() if v is not None}
        method = method.upper()
        try:
            if method == "GET":
                resp = client.get(url, params=params)
            elif method == "POST":
                resp = client.post(url, params=params, json=body if body else None)
            elif method == "PUT":
                resp = client.put(url, params=params, json=body if body else None)
            elif method == "PATCH":
                resp = client.patch(url, params=params, json=body if body else None)
            elif method == "DELETE":
                resp = client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            resp.raise_for_status()
            if resp.status_code == 204 or not resp.content:
                return {"status": "success", "code": resp.status_code}
            return resp.json()
        except httpx.HTTPStatusError as e:
            from openapi_client.exceptions import ApiException
            raise ApiException(status=e.response.status_code, reason=str(e), body=e.response.text)

    def select_header_accept(self, accepts):
        if not accepts:
            return None
        for accept in accepts:
            if "application/json" in accept:
                return accept
        return accepts[0]

    def select_header_content_type(self, content_types):
        if not content_types:
            return "application/json"
        for ct in content_types:
            if "application/json" in ct:
                return ct
        return content_types[0]

    def __del__(self):
        if self._client:
            self._client.close()
