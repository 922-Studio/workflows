"""Generate an isolated Docker Compose config for smoke testing.

Reads a compose file via `docker compose config --format json`, strips
container_name directives, remaps host ports to 0 (random), and prefixes
named volumes — so the smoke stack can run alongside production without
conflicts.

Usage:
    python generate_smoke_compose.py \
        --compose-file docker-compose.yaml \
        --output smoke-compose.json \
        --project smoke-12345
"""

import argparse
import json
import subprocess
import sys


def resolve_compose(compose_file: str) -> dict:
    """Run docker compose config to get the fully resolved compose spec."""
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "config", "--format", "json"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: docker compose config failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def isolate_config(config: dict, project: str) -> dict:
    """Modify a compose config for isolated smoke testing."""
    services = config.get("services", {})

    for name, svc in services.items():
        # Remove container_name so docker compose uses project prefix
        svc.pop("container_name", None)

        # Remap host ports to 0 (random) to avoid conflicts
        if "ports" in svc:
            new_ports = []
            for port in svc["ports"]:
                if isinstance(port, dict):
                    # Compose v2 format: {"target": 8080, "published": "8080", ...}
                    port["published"] = "0"
                    port.pop("host_ip", None)  # Remove host IP binding
                    new_ports.append(port)
                elif isinstance(port, str):
                    # String format: "8080:8080" or "127.0.0.1:5432:5432"
                    parts = port.split(":")
                    container_port = parts[-1]
                    new_ports.append(f"0:{container_port}")
                else:
                    new_ports.append(port)
            svc["ports"] = new_ports

        # Remove restart policy — smoke containers should not restart
        svc.pop("restart", None)

        # Remove env_file references (may not exist in smoke context)
        # Keep environment variables that are already resolved
        svc.pop("env_file", None)

    # Prefix named volumes to avoid conflicts with production
    volumes = config.get("volumes", {})
    if volumes:
        new_volumes = {}
        for vol_name, vol_config in volumes.items():
            new_name = f"{project}_{vol_name}"
            new_volumes[vol_name] = vol_config or {}
            new_volumes[vol_name]["name"] = new_name
        config["volumes"] = new_volumes

    # Remove networks with fixed names to avoid conflicts
    networks = config.get("networks", {})
    if networks:
        for net_name, net_config in networks.items():
            if net_config and "name" in net_config:
                del net_config["name"]

    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate isolated smoke compose config")
    parser.add_argument("--compose-file", required=True, help="Source compose file")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--project", required=True, help="Smoke project name for volume prefixing")
    args = parser.parse_args()

    print(f"📄 Reading compose config from: {args.compose_file}")
    config = resolve_compose(args.compose_file)

    service_names = list(config.get("services", {}).keys())
    print(f"🐳 Found services: {', '.join(service_names)}")

    print(f"🔧 Isolating config for project: {args.project}")
    isolated = isolate_config(config, args.project)

    with open(args.output, "w") as f:
        json.dump(isolated, f, indent=2)

    print(f"✅ Wrote isolated compose config to: {args.output}")


if __name__ == "__main__":
    main()
