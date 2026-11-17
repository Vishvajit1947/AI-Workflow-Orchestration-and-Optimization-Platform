/**
 * Turn any thrown value (usually an axios error from the FastAPI backend) into a readable message.
 */

interface ValidationIssue {
  msg?: string;
}

interface ApiErrorShape {
  response?: { data?: { detail?: unknown; message?: unknown } };
  message?: unknown;
}

const DEFAULT_MESSAGE = 'An unexpected error occurred';

/** FastAPI sends `detail` as a string, or as a list of issues for 422 validation errors. */
const detailToString = (detail: unknown): string | null => {
  if (typeof detail === 'string' && detail) return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((d: ValidationIssue | string) => (typeof d === 'string' ? d : d?.msg))
      .filter((m): m is string => Boolean(m));
    return messages.length ? messages.join('; ') : null;
  }
  return null;
};

/**
 * Prefer the backend's own explanation. Without one, use `fallback` when the caller has a
 * friendlier message for that screen, otherwise the transport error (e.g. "Network Error").
 */
export function getErrorMessage(error: unknown, fallback?: string): string {
  if (typeof error === 'object' && error !== null) {
    const e = error as ApiErrorShape;
    const data = e.response?.data;
    const fromApi = detailToString(data?.detail) ?? (typeof data?.message === 'string' && data.message ? data.message : null);
    if (fromApi) return fromApi;
    if (fallback) return fallback;
    if (typeof e.message === 'string' && e.message) return e.message;
  }
  return fallback ?? DEFAULT_MESSAGE;
}
