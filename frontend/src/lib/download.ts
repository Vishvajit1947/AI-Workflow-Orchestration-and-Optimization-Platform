/**
 * Browser downloads for generated files and server exports.
 */

const MIME_TYPES: Record<string, string> = {
  json: 'application/json', md: 'text/markdown', html: 'text/html', css: 'text/css',
  js: 'text/javascript', mjs: 'text/javascript', csv: 'text/csv', xml: 'application/xml',
  yaml: 'application/yaml', yml: 'application/yaml', sql: 'application/sql',
};

export const basename = (path: string) => path.slice(path.lastIndexOf('/') + 1);

/** "Binary Trees!" → "binary-trees" (mirrors the backend's safe_filename). */
export const safeFileStem = (name: string, fallback = 'output') =>
  name.toLowerCase().replace(/[^a-z0-9._-]+/g, '-').replace(/^[-._]+|[-._]+$/g, '').slice(0, 80) || fallback;

export const saveBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
};

/** Save a generated file under its own name and extension (never converted to .txt). */
export const saveTextFile = (content: string, path: string) => {
  const name = basename(path);
  const ext = name.includes('.') ? name.slice(name.lastIndexOf('.') + 1).toLowerCase() : '';
  saveBlob(new Blob([content], { type: `${MIME_TYPES[ext] ?? 'text/plain'};charset=utf-8` }), name);
};

const readBlobText = (blob: Blob): Promise<string> =>
  typeof blob.text === 'function'
    ? blob.text()
    : new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(reader.error);
        reader.readAsText(blob);
      });

/** Readable message from a failed download (the API sends JSON `detail`, even for blob requests). */
export const downloadErrorMessage = async (error: unknown): Promise<string> => {
  const data = (error as { response?: { data?: unknown } })?.response?.data;
  try {
    const parsed = data instanceof Blob ? JSON.parse(await readBlobText(data)) : data;
    const detail = (parsed as { detail?: unknown })?.detail;
    if (detail) return String(detail);
  } catch {
    // not JSON: fall through to the generic message
  }
  return (error as Error)?.message || 'Download failed';
};
