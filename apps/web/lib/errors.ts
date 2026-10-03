export class ApiError extends Error {
  readonly status: number;
  /** The API's structured `detail` (for example the ALERT_CHANGED object), when it sent one. */
  readonly detail?: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}
