export class AmberClawError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "AmberClawError";
  }
}

export class AmberClawAPIError extends AmberClawError {
  public readonly code: string;
  public readonly status: number;
  public readonly requestId?: string;

  constructor(message: string, code = "API_ERROR", status = 500, requestId?: string) {
    super(message);
    this.name = "AmberClawAPIError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

export class AmberClawAuthError extends AmberClawAPIError {
  constructor(message = "Authentication credentials missing or invalid", requestId?: string) {
    super(message, "AUTH_ERROR", 401, requestId);
    this.name = "AmberClawAuthError";
  }
}

export class AmberClawTimeoutError extends AmberClawError {
  constructor(message = "Request timed out") {
    super(message);
    this.name = "AmberClawTimeoutError";
  }
}
