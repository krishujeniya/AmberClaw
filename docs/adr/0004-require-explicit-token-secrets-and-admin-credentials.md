# 0004: Explicit token configuration and credential administration

Date: 2026-11-07. Status: accepted locally; target acceptance remains open.

The API previously accepted public default client credentials and signed tokens
with a public fallback key. Credential creation, rotation, revocation and
emergency elevation lacked an administrator dependency. Refresh tokens could
also be presented as ordinary API access tokens.

Require explicitly configured AUTH_CLIENT_ID, AUTH_CLIENT_SECRET and
JWT_SECRET_KEY. Both secrets must be at least32 bytes; reject the known public
signing fallback. Unsafe/missing configuration disables token issuance with503.
A configured service API key remains a separate authentication path. Compare
credentials in constant time. Issuers and verifiers share one secret accessor.

Use PyJWT with fixed HS256 for application tokens, require expiration/subject,
and reject refresh tokens at ordinary API authorization. OIDC separately permits
only issuer-key RS256/ES256 ID tokens. Remove python-jose from the dependency
graph/environment rather than ignoring its unpatched advisory. Credential
administration requires an authenticated administrator. Negative tests verify
401/403 before mutation; configured admin lifecycle tests still pass. Test
credentials are ephemeral random values scoped to pytest.

Changing the signing key invalidates existing tokens. Configure the same secret
across intended workers using the deployment's secret storage/rotation process.
This does not establish persistent cross-worker revocation, complete resource
ownership/tenant authorization, or independent security acceptance.

References: [PyJWT API guidance](https://pyjwt.readthedocs.io/en/stable/api.html)
and [python-jose advisory](https://github.com/advisories/GHSA-3qf3-8w2g-rqmx).
