"""Unit tests for deployment manifests and security hardening."""

from pathlib import Path

import yaml


def test_docker_compose_prod_hardening():
    compose_file = Path("deploy/docker/docker-compose.prod.yml")
    assert compose_file.exists()

    content = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    assert "services" in content
    services = content["services"]

    # 1. Gateway Service Validation
    assert "amberclaw-gateway" in services
    gateway = services["amberclaw-gateway"]

    # Non-root user identity
    assert gateway.get("user") == "10001:10001"

    # Security options
    security_opts = gateway.get("security_opt", [])
    assert "no-new-privileges:true" in security_opts

    # Resource limits
    deploy_cfg = gateway.get("deploy", {})
    resources = deploy_cfg.get("resources", {})
    limits = resources.get("limits", {})
    assert "cpus" in limits
    assert "memory" in limits

    # Localhost loopback port binding for security
    ports = gateway.get("ports", [])
    assert any("127.0.0.1:8000:8000" in p for p in ports)

    # 2. ChromaDB Service Validation
    assert "chromadb" in services
    chroma = services["chromadb"]
    chroma_security = chroma.get("security_opt", [])
    assert "no-new-privileges:true" in chroma_security


def test_docker_compose_airgapped_profile():
    compose_file = Path("deploy/docker/docker-compose.airgapped.yml")
    assert compose_file.exists()

    content = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    assert "services" in content
    services = content["services"]
    networks = content.get("networks", {})

    # 1. Network isolation (Strict zero-egress internal network)
    assert "amberclaw-airgap-net" in networks
    assert networks["amberclaw-airgap-net"].get("internal") is True

    # 2. Gateway Service Validation
    assert "amberclaw-gateway" in services
    gateway = services["amberclaw-gateway"]
    assert gateway.get("user") == "10001:10001"
    assert "no-new-privileges:true" in gateway.get("security_opt", [])
    assert "amberclaw-airgap-net" in gateway.get("networks", [])

    env_vars = gateway.get("environment", [])
    assert any("OFFLINE_MODE=true" in env for env in env_vars)

    # 3. Local Inference (Ollama) Validation
    assert "ollama" in services
    ollama = services["ollama"]
    assert "amberclaw-airgap-net" in ollama.get("networks", [])
    assert "no-new-privileges:true" in ollama.get("security_opt", [])

    # 4. Local Vector DB Validation
    assert "chromadb" in services
    chroma = services["chromadb"]
    assert "amberclaw-airgap-net" in chroma.get("networks", [])


def test_dockerfile_gateway_security():
    dockerfile = Path("deploy/docker/Dockerfile.gateway")
    assert dockerfile.exists()
    content = dockerfile.read_text(encoding="utf-8")

    # Non-root user creation and switch
    assert "useradd" in content or "adduser" in content
    assert "USER" in content
    # Health check instruction or exposure
    assert "EXPOSE 8000" in content


def test_helm_chart_security_and_values():
    chart_file = Path("deploy/k8s/helm/Chart.yaml")
    values_file = Path("deploy/k8s/helm/values.yaml")
    deployment_template = Path("deploy/k8s/helm/templates/deployment.yaml")

    assert chart_file.exists()
    assert values_file.exists()
    assert deployment_template.exists()

    chart_meta = yaml.safe_load(chart_file.read_text(encoding="utf-8"))
    assert chart_meta["name"] == "amberclaw"
    assert "version" in chart_meta

    values = yaml.safe_load(values_file.read_text(encoding="utf-8"))

    # Non-root security context
    sec_ctx = values.get("securityContext", {})
    assert sec_ctx.get("runAsNonRoot") is True
    assert "ALL" in sec_ctx.get("capabilities", {}).get("drop", [])

    # Resource requests and limits
    resources = values.get("resources", {})
    assert "limits" in resources
    assert "requests" in resources
    assert resources["limits"]["memory"] == "1024Mi"

    # Probes in deployment template
    deploy_tpl_content = deployment_template.read_text(encoding="utf-8")
    assert "livenessProbe" in deploy_tpl_content
    assert "readinessProbe" in deploy_tpl_content
    assert "path: /health" in deploy_tpl_content
    assert "topologySpreadConstraints" in deploy_tpl_content
    assert "podAntiAffinity" in deploy_tpl_content
    assert "terminationGracePeriodSeconds" in deploy_tpl_content
    assert "preStop" in deploy_tpl_content


def test_helm_pdb_and_external_secrets_templates():
    pdb_file = Path("deploy/k8s/helm/templates/pdb.yaml")
    ext_secret_file = Path("deploy/k8s/helm/templates/externalsecret.yaml")
    schema_file = Path("deploy/k8s/helm/values.schema.json")

    assert pdb_file.exists()
    assert ext_secret_file.exists()
    assert schema_file.exists()

    pdb_content = pdb_file.read_text(encoding="utf-8")
    assert "kind: PodDisruptionBudget" in pdb_content
    assert "minAvailable" in pdb_content

    ext_content = ext_secret_file.read_text(encoding="utf-8")
    assert "kind: ExternalSecret" in ext_content
    assert "secretStoreRef" in ext_content


def test_release_engineering_scripts():
    from scripts.enforce_semver import validate_semver  # noqa: PLC0415
    from scripts.generate_release_notes import (  # noqa: PLC0415
        build_release_notes,
        categorize_commits,
    )

    # SemVer tests
    assert validate_semver("2026.0.1")
    assert validate_semver("1.2.3-alpha.1")
    assert validate_semver("v2.0.0")
    assert not validate_semver("2026.invalid")

    # Release notes generator tests
    mock_commits = [
        "a1b2c3d feat(core): implement kernel supervisor",
        "e4f5a6b sec: zero memory on sensitive secret wipe",
        "c7d8e9f fix: catch timeout error in gateway",
    ]
    categorized = categorize_commits(mock_commits)
    assert len(categorized["🚀 Features"]) == 1
    assert len(categorized["🛡️ Security & Zero-Trust"]) == 1
    assert len(categorized["🐞 Bug Fixes"]) == 1

    notes = build_release_notes("2026.0.1", categorized)
    assert "Release Notes" in notes
    assert "implement kernel supervisor" in notes
