import assert from "node:assert";
import test from "node:test";
import { AmberClawClient } from "./client.js";
import { AmberClawAPIError, AmberClawAuthError } from "./errors.js";

test("AmberClawClient initializes with default baseURL and custom headers", () => {
  const client = new AmberClawClient({ apiKey: "ak_test_12345" });
  assert.ok(client);

  const jwtClient = new AmberClawClient({ token: "jwt_bearer_token" });
  assert.ok(jwtClient);
});

test("AmberClawError classes inherit correctly", () => {
  const apiErr = new AmberClawAPIError("Invalid query", "INVALID_PARAM", 400, "req_999");
  assert.strictEqual(apiErr.code, "INVALID_PARAM");
  assert.strictEqual(apiErr.status, 400);
  assert.strictEqual(apiErr.requestId, "req_999");

  const authErr = new AmberClawAuthError("Expired token", "req_auth_1");
  assert.strictEqual(authErr.status, 401);
  assert.strictEqual(authErr.code, "AUTH_ERROR");
});
