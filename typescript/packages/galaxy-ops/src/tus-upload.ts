/**
 * Thin wrapper around tus-js-client for uploading a local file to the Galaxy
 * resumable-upload endpoint. Isolated here so op tests can vi.mock this module
 * without hitting real network.
 *
 * The session_id is the final path segment of the URL the tus server assigns
 * (same derivation as BioBlend's _tus_uploader_session_id monkeypatch).
 */

import { readFileSync, statSync } from "node:fs";
import { basename } from "node:path";
import { DefaultHttpStack, DetailedError, Upload, type HttpRequest, type HttpStack } from "tus-js-client";
import {
  GalaxyConnectionError,
  GalaxyError,
  GalaxyValidationError,
  isRedirectStatus,
  redirectRefusal,
  redirectTarget,
} from "./errors";

export interface TusUploadOptions {
  baseUrl: string;
  apiKey: string;
  path: string;
  signal?: AbortSignal;
}

const UPLOAD_ROUTE = "/api/upload/resumable_upload";

/**
 * The upload's path and query, if `location` names an upload under `prefix`; else undefined.
 *
 * Decided on the raw string, before any URL parser has had the chance to collapse a `..` or
 * a `%2e%2e` into a path that looks fine. Strict on purpose: Galaxy's upload ids are one plain
 * segment, so anything that needs dots, slashes, escapes or backslashes to spell is refused.
 * The fragment is dropped (it is never sent anyway); the query is kept, since it belongs to
 * the upload and goes to the configured origin with everything else.
 */
export function uploadPathIn(location: string, prefix: string): string | undefined {
  const noFragment = location.split("#")[0]!;
  const authority = /^(?:[A-Za-z][A-Za-z0-9+.-]*:)?\/\/[^/?#\\]*/.exec(noFragment);
  const rest = authority ? noFragment.slice(authority[0].length) : noFragment;
  const q = rest.indexOf("?");
  const path = q === -1 ? rest : rest.slice(0, q);
  const query = q === -1 ? "" : rest.slice(q);
  if (!path.startsWith(prefix)) return undefined;
  if (!/^[A-Za-z0-9_-]+$/.test(path.slice(prefix.length))) return undefined;
  return path + query;
}

/**
 * Upload `path` over tus and hand back the session id Galaxy's fetch API takes.
 *
 * Galaxy's tus server answers the creation POST with an ABSOLUTE Location built from the Host
 * it saw (or X-Forwarded-Host/Proto behind a proxy), and tus sends every later request there,
 * key and all. So the Location is never dialled as given: its path must be this Galaxy's upload
 * route, and the request goes to the configured origin with that path. The key only ever
 * reaches the configured Galaxy, and a deployment reached by an internal name whose proxy
 * forwards the public one keeps working. A Location that is not the upload route is refused,
 * once -- not retried. (Node's http stack never follows a 3xx, and tus fails on one.)
 */
export function tusUploadFile(opts: TusUploadOptions): Promise<string> {
  return new Promise((resolve, reject) => {
    const { apiKey, path, signal } = opts;
    const baseUrl = opts.baseUrl.replace(/\/+$/, "");
    const file = basename(path);
    const data = readFileSync(path);
    const size = statSync(path).size;

    const endpoint = `${baseUrl}${UPLOAD_ROUTE}`;
    const base = new URL(baseUrl);
    const prefix = `${base.pathname.replace(/\/+$/, "")}${UPLOAD_ROUTE}/`;

    const refuse = (where: string) =>
      new GalaxyConnectionError(
        `tus upload refused: Galaxy's upload Location ${where} is not its resumable-upload ` +
          "route, so the API key was not sent to it",
      );

    /** Where a request for `url` actually goes: the endpoint as is, an upload re-rooted. */
    const reroot = (url: string): string => {
      if (url === endpoint) return url;
      const kept = uploadPathIn(url, prefix);
      if (kept === undefined) throw refuse(url);
      const target = `${base.origin}${kept}`;
      // Checked again on what is about to be sent, not just on what was asked for.
      const sent = new URL(target);
      if (sent.origin !== base.origin || `${sent.pathname}${sent.search}` !== kept) {
        throw refuse(url);
      }
      return target;
    };

    const inner = new DefaultHttpStack({});
    const httpStack: HttpStack = {
      getName: () => "GalaxyRerootedHttpStack",
      createRequest(method: string, url: string): HttpRequest {
        let target: string;
        try {
          target = reroot(url);
        } catch (err) {
          const req = inner.createRequest(method, endpoint);
          req.send = () => Promise.reject(err);
          return req;
        }
        return inner.createRequest(method, target);
      },
    };

    const upload = new Upload(data, {
      endpoint,
      httpStack,
      headers: { "x-api-key": apiKey },
      metadata: { filename: file, filetype: "application/octet-stream" },
      uploadSize: size,
      retryDelays: [0, 1000, 3000],
      onAfterResponse(req, res) {
        const status = res.getStatus();
        const location = res.getHeader("Location");
        // A redirect on any tus request is refused the way every other op refuses one -- a
        // proxy's http -> https hop is a GALAXY_URL to fix -- and never retried.
        if (isRedirectStatus(status)) {
          throw new GalaxyValidationError(
            redirectRefusal(status, location ? redirectTarget(location, req.getURL()) : undefined),
          );
        }
        // The raw header, before tus resolves it into a URL and normalises the path. Only a
        // 2xx creation reply names the upload.
        if (
          status >= 200 &&
          status < 300 &&
          req.getMethod() === "POST" &&
          location &&
          uploadPathIn(location, prefix) === undefined
        ) {
          throw refuse(location);
        }
      },
      onShouldRetry(err) {
        if (refusalIn(err)) return false;
        const status = err.originalResponse ? err.originalResponse.getStatus() : 0;
        return !(status >= 400 && status < 500) || status === 409 || status === 423;
      },
      onSuccess() {
        // upload.url is the canonical tus upload location set from the creation 201 Location.
        const sessionId = (upload.url ?? "").split(/[?#]/)[0]!.split("/").pop() ?? "";
        if (!sessionId) {
          reject(new Error("tus upload succeeded but session_id could not be derived from upload URL"));
          return;
        }
        resolve(sessionId);
      },
      onError(err) {
        reject(refusalIn(err) ?? err);
      },
    });
    // Wire AbortSignal -> tus abort
    if (signal) {
      if (signal.aborted) {
        upload.abort(false).catch(() => {});
        reject(new DOMException("Aborted", "AbortError"));
        return;
      }
      signal.addEventListener("abort", () => {
        upload.abort(false).catch(() => {});
        reject(new DOMException("Aborted", "AbortError"));
      }, { once: true });
    }

    upload.start();
  });
}

/** One of our own refusals (a bad Location, a redirect): final, and handed back as is. */
function refusalIn(err: unknown): GalaxyError | undefined {
  if (err instanceof GalaxyError) return err;
  const cause = err instanceof DetailedError ? err.causingError : undefined;
  return cause instanceof GalaxyError ? cause : undefined;
}
