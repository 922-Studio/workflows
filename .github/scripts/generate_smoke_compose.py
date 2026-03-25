"""Generate an isolated Docker Compose config for smoke testing.

Reads a compose file via `docker compose config --format json`, strips
container_name directives, remaps host ports to 0 (random), prefixes
named volumes, isolates external networks, and injects temporary
database/cache services — so the smoke stack can run alongside production
without conflicts or side effects on production data.

Usage:
    python generate_smoke_compose.py \
        --compose-file docker-compose.yaml \
        --output smoke-compose.json \
        --project smoke-12345
"""

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import urlparse

# Hostnames of shared infrastructure that must be replaced with temp services
EXTERNAL_POSTGRES_HOSTS = {"shared_postgres", "dev_postgres"}
EXTERNAL_REDIS_HOSTS = {"shared_redis", "dev_redis"}

# Names for injected temporary services
SMOKE_POSTGRES = "smoke-postgres"
SMOKE_REDIS = "smoke-redis"


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

    # Isolate external networks — remove 'external' flag so docker compose
    # creates project-scoped networks instead of joining production ones.
    # This prevents smoke containers from reaching shared_postgres, shared_redis, etc.
    networks = config.get("networks", {})
    if networks:
        for net_name, net_config in networks.items():
            if isinstance(net_config, dict):
                net_config.pop("external", None)
                net_config.pop("name", None)

    return config


def isolate_external_services(config: dict) -> dict:
    """Replace references to shared infrastructure with temporary isolated services.

    Scans all service environment variables for references to shared PostgreSQL
    and Redis hosts. When found, rewrites the connection strings to point to
    temporary services and injects those services into the compose config.

    This ensures smoke tests never touch production databases — migrations run
    against an ephemeral PostgreSQL that is destroyed after the test.
    """
    services = config.get("services", {})
    networks = config.get("networks", {})
    all_network_names = list(networks.keys())

    pg_credentials: dict[str, dict[str, str]] = {}  # {db_name: {user, password}}
    needs_redis = False

    for svc_name, svc in services.items():
        env = svc.get("environment", {})
        for key, val in list(env.items()):
            if not isinstance(val, str):
                continue

            # Rewrite PostgreSQL references to shared hosts
            for ext_host in EXTERNAL_POSTGRES_HOSTS:
                if ext_host in val:
                    try:
                        clean = re.sub(r"postgresql\+\w+://", "postgresql://", val)
                        parsed = urlparse(clean)
                        db_user = parsed.username or "smoke"
                        db_pass = parsed.password or "smoke"
                        db_name = (parsed.path or "/smoke").lstrip("/") or "smoke"
                        pg_credentials[db_name] = {
                            "user": db_user,
                            "password": db_pass,
                        }
                    except Exception:
                        pg_credentials.setdefault(
                            "smoke", {"user": "smoke", "password": "smoke"}
                        )
                    env[key] = val.replace(ext_host, SMOKE_POSTGRES)

            # Rewrite Redis references to shared hosts
            for ext_host in EXTERNAL_REDIS_HOSTS:
                if ext_host in val:
                    needs_redis = True
                    env[key] = val.replace(ext_host, SMOKE_REDIS)

    # Inject temporary PostgreSQL
    if pg_credentials:
        first_db_name, first_creds = next(iter(pg_credentials.items()))
        pg_service: dict = {
            "image": "postgres:16-alpine",
            "environment": {
                "POSTGRES_USER": first_creds["user"],
                "POSTGRES_PASSWORD": first_creds["password"],
                "POSTGRES_DB": first_db_name,
            },
            "healthcheck": {
                "test": ["CMD-SHELL", f"pg_isready -U {first_creds['user']}"],
                "interval": "3s",
                "timeout": "3s",
                "retries": 10,
            },
        }
        if all_network_names:
            pg_service["networks"] = {n: None for n in all_network_names}
        services[SMOKE_POSTGRES] = pg_service

        # Add depends_on so app services wait for the DB to be ready
        for svc_name, svc in services.items():
            if svc_name in (SMOKE_POSTGRES, SMOKE_REDIS):
                continue
            env = svc.get("environment", {})
            if any(isinstance(v, str) and SMOKE_POSTGRES in v for v in env.values()):
                depends_on = svc.get("depends_on", {})
                if isinstance(depends_on, list):
                    depends_on = {d: {"condition": "service_started"} for d in depends_on}
                depends_on[SMOKE_POSTGRES] = {"condition": "service_healthy"}
                svc["depends_on"] = depends_on

        print(f"  injected {SMOKE_POSTGRES} (db: {first_db_name}, user: {first_creds['user']})")

    # Inject temporary Redis
    if needs_redis:
        redis_service: dict = {
            "image": "redis:7-alpine",
            "healthcheck": {
                "test": ["CMD", "redis-cli", "ping"],
                "interval": "3s",
                "timeout": "3s",
                "retries": 10,
            },
        }
        if all_network_names:
            redis_service["networks"] = {n: None for n in all_network_names}
        services[SMOKE_REDIS] = redis_service

        print(f"  injected {SMOKE_REDIS}")

    return config


def apply_prebuilt_image(config: dict, prebuilt_image: str) -> dict:
    """Replace all build: sections with a fixed image reference.

    When a pre-built image is provided (e.g. from a prior build job in the
    pipeline), there is no need to re-build from source.  Every service that
    previously had a ``build:`` directive is updated to use the supplied image
    instead.  Services that already declare an ``image:`` without a ``build:``
    (e.g. postgres, redis) are left unchanged.
    """
    services = config.get("services", {})
    patched = []

    for name, svc in services.items():
        if "build" in svc:
            svc.pop("build")
            svc["image"] = prebuilt_image
            patched.append(name)

    if patched:
        print(f"  replaced build: with image: {prebuilt_image} for services: {', '.join(patched)}")
    else:
        print("  no build: sections found; --prebuilt-image had no effect")

    return config


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate isolated smoke compose config")
    parser.add_argument("--compose-file", required=True, help="Source compose file")
    parser.add_argument("--output", required=True, help="Output file path")
    parser.add_argument("--project", required=True, help="Smoke project name for volume prefixing")
    parser.add_argument(
        "--prebuilt-image",
        default=None,
        help=(
            "Pre-built image to use instead of building from source "
            "(e.g. registry.922-studio.com/drafter:dev-v1.2.3). "
            "Replaces all 'build:' sections in the compose config."
        ),
    )
    args = parser.parse_args()

    print(f"Reading compose config from: {args.compose_file}")
    config = resolve_compose(args.compose_file)

    service_names = list(config.get("services", {}).keys())
    print(f"Found services: {', '.join(service_names)}")

    if args.prebuilt_image:
        print(f"Applying pre-built image: {args.prebuilt_image}")
        config = apply_prebuilt_image(config, args.prebuilt_image)

    print(f"Isolating config for project: {args.project}")
    isolated = isolate_config(config, args.project)

    print("Isolating external service references...")
    isolated = isolate_external_services(isolated)

    with open(args.output, "w") as f:
        json.dump(isolated, f, indent=2)

    print(f"Wrote isolated compose config to: {args.output}")


if __name__ == "__main__":
    main()
