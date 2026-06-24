"""Patch generated API stub methods to make real HTTP calls via api_client.call_api()."""

import os
import re
import sys

API_DIR = sys.argv[1] if len(sys.argv) > 1 else "/home/lab/openclaw/mcp-servers/homeapi/generated_openapi/openapi_client/api"


def patch_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    original = content

    # Match method def + docstring + pass
    method_pattern = re.compile(
        r"(    def (\w+)\(self(?:,\s*([^)]*))?\)\s*->\s*\w+:\s*\n"
        r"        \"\"\"(.*?)\"\"\")\s*\n"
        r"        pass",
        re.DOTALL,
    )

    def generate_impl(match):
        full_sig = match.group(1)
        method_name = match.group(2)
        params_str = match.group(3) or ""
        docstring = match.group(4)

        # Skip _with_http_info variants
        if method_name.endswith("_with_http_info"):
            return match.group(0)

        # Extract HTTP method and path from docstring
        http_match = re.search(r"(GET|POST|PUT|PATCH|DELETE)\s+(/\S+)", docstring)
        if not http_match:
            return match.group(0)

        http_method = http_match.group(1)
        path = http_match.group(2)

        # Parse parameters
        params = []
        if params_str:
            for p in params_str.split(","):
                p = p.strip()
                if p.startswith("**"):
                    continue
                name = re.match(r"(\w+)", p)
                if name:
                    pname = name.group(1)
                    params.append(pname)

        # Path params from {param} in path
        path_param_names = set(re.findall(r"\{(\w+)\}", path))

        # Build implementation
        lines = [full_sig]

        path_params = [n for n in params if n in path_param_names]
        query_params = [n for n in params if n not in path_param_names and n != "body"]
        has_body = "body" in params

        if path_params:
            pp_items = ", ".join(f'"{n}": {n}' for n in path_params)
            lines.append(f"        path_params = {{{pp_items}}}")
        else:
            lines.append("        path_params = None")

        if query_params:
            qp_items = ", ".join(f'"{n}": {n}' for n in query_params)
            lines.append(f"        query_params = {{{qp_items}}}")
        else:
            lines.append("        query_params = None")

        if has_body:
            lines.append("        import json as _json")
            lines.append("        _body = _json.loads(body) if isinstance(body, str) else body")
            body_arg = ", body=_body"
        else:
            body_arg = ""

        lines.append(
            f'        return self.api_client.call_api("{path}", "{http_method}", '
            f"path_params=path_params, query_params=query_params{body_arg})"
        )

        return "\n".join(lines)

    content = method_pattern.sub(generate_impl, content)

    if content != original:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


# Patch all API files
patched = 0
for filename in sorted(os.listdir(API_DIR)):
    if filename.endswith("_api.py") and filename != "__init__.py":
        filepath = os.path.join(API_DIR, filename)
        if patch_file(filepath):
            patched += 1
            print(f"  Patched: {filename}")

print(f"\nPatched {patched} API files")
