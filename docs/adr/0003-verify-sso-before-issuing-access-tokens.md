# 0003: Verify SSO credentials before issuing access tokens

Date: 2026-11-07. Status: accepted locally; target IdP acceptance remains open.

The previous callback issued access tokens from unsigned SAML XML and JSON OIDC
claims. Neither establishes an authenticated identity. Its positive tests encoded
the vulnerability rather than testing an identity provider's proof.

Use python3-saml in strict mode with an administrator-pinned IdP certificate,
signed assertions, schema validation, issuer, audience, destination, time and
request correlation checks. Use OIDC discovery from the configured HTTPS issuer,
an authorization-code exchange with PKCE, and Authlib ID-token verification
against the discovered JWKS. Accept only RS256/ES256 and validate issuer,
audience, expiry, issued time, authorized party and the request nonce.

Both flows require a five-minute, single-use pending request and a matching
Secure, HttpOnly browser cookie. SSO defaults to disabled. Unsolicited SAML and raw
OIDC claims cannot issue tokens. Configuration changes clear pending requests.
Callbacks must reach the configured HTTPS ACS URL; proxy forwarding must be
configured correctly by the operator.

Pending requests are deliberately bounded and process-local. A restart loses
pending logins and fails closed. Multi-worker operation needs session affinity or
a shared, atomic consume store before acceptance. Live IdP compatibility,
certificate rotation and deployment proxy behavior require target verification.

Offline tests sign ephemeral SAML assertions and ID tokens using real keys and
exercise valid logins, tampering, wrong issuer/audience/recipient/nonce,
expiration, browser mismatch, disabled configuration and replay. These tests
establish local behavior, not independent security or production acceptance.

References: [SAML toolkit security guidance](https://github.com/SAML-Toolkits/python3-saml#security-warning)
and [OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation).
