# ADR-0002: Bind the private dashboard to explicit runtime services

Date: 7 November 2026
Status: accepted for the local stabilization implementation; release acceptance open

The dashboard previously returned invented sessions, usage, audit entries and chat
execution status. Its data routes did not require a session. Constructing the
standalone application also provided no canonical agent runtime to execute chat.

`create_web_app` accepts typed `DashboardServices` and a `WebAuthManager`. Data and
chat routes require a valid dashboard session. Configured credentials are required;
there are no default admin credentials. Missing service bindings produce empty or
unavailable measurements; chat returns 503 before dispatch when no runtime exists.
The public health route measures only HTTP process availability. It does not
attest to model, channel, sandbox, database or policy health.

The authentication cookie is an HttpOnly credential. An independent conversation
identifier supplies agent routing and persisted session keys. The cookie is not
included in login JSON, prompts, chat IDs or conversation keys. Direct processing
shares AgentLoop's bus-processing lock to protect mutable tool/routing context.

This makes service ownership explicit and permits deterministic tests without
model calls. The standalone application remains unavailable for chat until its
caller supplies a runtime. Wiring production services and verifying their actual
behavior are separate acceptance work. Dependency injection and local tests do
not establish deployment, tenant isolation or an independent security assessment.
