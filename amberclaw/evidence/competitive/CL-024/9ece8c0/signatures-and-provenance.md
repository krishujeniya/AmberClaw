# CL-024: Artifact Signatures, SBOM, and Build Provenance

## 1. Build Provenance Specification
- **Package**: `amberclaw-2026.0.1-py3-none-any.whl`
- **Build Backend**: `hatchling.build`
- **Compiler / Python**: CPython 3.11.13 on Linux x86_64
- **Deterministic Checksum (SHA-256)**:
  `c3e976493e00717989fac3f4a128937172f5ee23fd4c94dc054bfeab5d2f5e48`

## 2. Supply Chain Security (SLSA Level 2 Alignment)
1. **Source Version Pinned**: Commit `9ece8c02f4ce31178bed489ca07f26af29d6d735`.
2. **Hermetic Lockfile**: All transitive wheel dependencies pinned via `uv.lock`.
3. **Secret Scan Verification**: Automated `SecretScanner.scan_workspace()` verified zero committed or unredacted credentials prior to artifact generation.
4. **License Compliance**: 100% of included third-party libraries licensed under permissive terms (MIT, Apache-2.0, BSD). Zero copyleft (GPL/AGPL) contamination.

## 3. Publication Authorization Gate
In accordance with standing repository policy, publication to public package repositories (e.g. PyPI) or external container registries requires separate explicit customer/maintainer authorization. Local build artifacts remain secured within `./dist` and the verified evidence bundle.
