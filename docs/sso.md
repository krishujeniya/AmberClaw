# Enterprise SSO

SSO is disabled by default. The application embedding the API must call
`set_sso_config(SSOConfig(enabled=True, ...))` with its actual service provider and
identity provider configuration. This setting is currently process-local.

For SAML, configure `sp_entity_id`, the HTTPS `sp_acs_url`, `idp_entity_id`,
`idp_sso_url` and a trusted PEM `idp_x509_cert`. The IdP must sign assertions and
include valid audience, recipient, request ID and validity conditions. Start at
`GET /api/v1/auth/sso/login`; the IdP POSTs a URL-encoded `SAMLResponse` and the
returned `RelayState` to the ACS. IdP-initiated unsolicited login is unsupported.

For OIDC, configure `protocol="oidc"`, `oidc_issuer_url`, `oidc_client_id`,
`oidc_client_secret` when required, and the HTTPS `sp_acs_url`. Register that exact
callback URL with the provider. Login discovers the provider's endpoints and
redirects with a random state, nonce and PKCE challenge. The callback accepts an
authorization code and state, exchanges the code server-side, and verifies the
signed ID token. Supplying a JSON claims dictionary cannot authenticate a user.

The browser must retain the Secure, HttpOnly SameSite=None login cookie. Callback
scheme, host and path must match the configured ACS; configure trusted proxy
forwarding before target testing. Requests expire after five minutes and cannot
be reused. A server restart or configuration change invalidates pending logins.
Use a single worker or session affinity until a shared atomic request store has
been implemented and verified. No live IdP or proxy acceptance is claimed here.

Offline verification:

```bash
LITELLM_LOCAL_MODEL_COST_MAP=True uv run pytest -q \
  tests/unit/security/test_sso.py tests/integration/test_sso_api.py \
  tests/security/test_oidc_verification.py
```

See [ADR 0003](adr/0003-verify-sso-before-issuing-access-tokens.md) for the security
boundary and implementation tradeoffs.
