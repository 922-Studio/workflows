"""Patch the generated MCP middleware to inject an X-Org-ID header on the stdio ApiClient.

The mcp-generator (openapi-py-fetch based) builds the stdio ApiClient as
`ApiClient(configuration=config)` with no org context. HomeAPI's org-scoped endpoints
(finance/ledger, health/sleep, ...) return 403 without an `X-Org-ID` header. This patch
rewrites the `_get_stdio_client()` body to pass the org header when HOMEAPI_ORG_ID is set,
using openapi_py_fetch.ApiClient's header_name/header_value parameters.

Idempotent: running twice is a no-op once patched.

Usage: python patch_middleware_org.py <path-to-authentication.py>
"""

import sys

TARGET = sys.argv[1] if len(sys.argv) > 1 else "middleware/authentication.py"

OLD = """            self._stdio_client = ApiClient(configuration=config)

        return self._stdio_client"""

NEW = """            org_id = os.getenv("HOMEAPI_ORG_ID")
            if org_id:
                self._stdio_client = ApiClient(
                    configuration=config,
                    header_name="X-Org-ID",
                    header_value=org_id,
                )
            else:
                self._stdio_client = ApiClient(configuration=config)

        return self._stdio_client"""


def main() -> int:
    with open(TARGET) as f:
        content = f.read()

    if "X-Org-ID" in content:
        print("  Middleware already patched with X-Org-ID — skipping")
        return 0

    if OLD not in content:
        print(f"  WARNING: expected _get_stdio_client body not found in {TARGET}.")
        print("  The generator output may have changed — patch NOT applied.")
        return 1

    content = content.replace(OLD, NEW)
    with open(TARGET, "w") as f:
        f.write(content)
    print(f"  Patched X-Org-ID injection into {TARGET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
