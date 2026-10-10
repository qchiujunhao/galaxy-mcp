import createClient, { type Client, type ClientOptions } from "openapi-fetch";
import type { GalaxyApiPaths } from "./bindings";
import {
  GalaxyConnectionError,
  GalaxyError,
  GalaxyValidationError,
  isRedirectStatus,
  redirectRefusal,
  redirectTarget,
  transportFailure,
} from "./errors";
import { rememberHttpFailure } from "./http-failure";

export type GalaxyClient = Client<GalaxyApiPaths>;

/**
 * Our own client over the bindings -- explicit baseUrl + x-api-key.
 * Deliberately NOT the published createGalaxyApi (it pins openapi-fetch ^0.12 and
 * defaults baseUrl to window.location.origin). `fetchImpl` is for tests only.
 *
 * The middleware is what lets a failure be worded the way the Python server words one.
 * Its sentences quote the reply -- as bytes, as text, or by the URL asked for -- and none
 * of the three survives openapi-fetch's own handling: it parses the error body and hands
 * back the parsed value, `Response.url` is empty for a reply a test built, and the method
 * is on the request. So the facts are taken while the reply is still whole, and filed
 * against it for the throw site to pick up.
 *
 * Redirects are never followed. A hop re-sends `x-api-key` to wherever the Location points,
 * so a Galaxy (or anything in front of it) answering 3xx could hand the key to another
 * origin. The Python server refuses the same hops: its GETs force `allow_redirects=False`
 * and bioblend already sends every write without following. No Galaxy API route a tool
 * calls answers with a redirect, so this costs nothing that works today.
 */
export function createGalaxyClient(
  baseUrl: string,
  apiKey: string,
  fetchImpl?: ClientOptions["fetch"],
): GalaxyClient {
  const guardedFetch = refuseRedirects(
    baseUrl,
    fetchImpl ?? ((input: Request) => globalThis.fetch(input)),
  );
  const client = createClient<GalaxyApiPaths>({
    baseUrl,
    headers: { "x-api-key": apiKey },
    redirect: "manual",
    fetch: guardedFetch,
  });
  client.use({
    onRequest({ request, options }) {
      // openapi-fetch takes `fetch`, `Request` and `baseUrl` per call as well, and a per-call
      // fetch would walk straight past the guard. Nothing here passes one; this keeps it so.
      // (The Request check compares against globalThis.Request as it is at call time.)
      if (options.fetch !== guardedFetch || request.constructor !== globalThis.Request) {
        throw new GalaxyConnectionError(
          "refusing a request that replaces the client's fetch or Request",
        );
      }
      return undefined;
    },
    async onResponse({ request, response }) {
      // Only a failure needs this, and only a failure pays for the extra read: cloning a
      // reply that is about to be parsed anyway would double the work on every success.
      if (!response.ok) {
        rememberHttpFailure(response, {
          status: response.status,
          method: request.method.toUpperCase(),
          url: request.url,
          bodyText: await response.clone().text(),
          reason: response.statusText,
        });
      }
      return undefined;
    },
    onError({ request, error }) {
      // Already one of ours, facts and all -- a redirect refused in the fetch wrapper.
      if (error instanceof GalaxyError) return error;
      // A request that never got a reply. The other server answers for this case too --
      // its client hands the tool a failure with no status on it -- so it is turned into
      // one of ours rather than left to escape as a bug.
      return transportFailure(request, error);
    },
  });
  return client;
}

type FetchImpl = NonNullable<ClientOptions["fetch"]>;

/**
 * The one place every request goes through, so it is where the no-redirect rule is held.
 *
 * `redirect: "manual"` on the client is the default, but openapi-fetch lets a per-call init
 * override it, and a per-call `baseUrl` too; refusing either here means no call site can opt
 * back in or point the key somewhere else. A 3xx is then thrown rather than returned, because
 * a redirect with an empty body would otherwise reach the ops as `{ error: undefined }` and
 * could be read as a success with no content.
 *
 * The kind is `validation`, not `connection`: the one redirect a real deployment sends is a
 * proxy's http -> https hop, which is a GALAXY_URL to fix, and retrying cannot fix it.
 */
function refuseRedirects(baseUrl: string, inner: FetchImpl): FetchImpl {
  return async (input: Request) => {
    if (input.redirect !== "manual") {
      throw new GalaxyConnectionError("refusing to send a request that would follow redirects");
    }
    if (!isUnderBase(input.url, baseUrl)) {
      throw new GalaxyConnectionError(`refusing to send the API key outside ${baseUrl}`);
    }
    const response = await inner(input);
    // A browser hands back an opaque redirect: status 0, no Location, nothing to quote.
    if (response.type === "opaqueredirect") {
      throw new GalaxyValidationError(redirectRefusal(null, undefined));
    }
    if (isRedirectStatus(response.status)) {
      const raw = response.headers.get("location") ?? undefined;
      // Only the stripped form is kept: the facts end up in the surface sentence too.
      const target = raw === undefined ? undefined : redirectTarget(raw, input.url);
      const failure = new GalaxyValidationError(redirectRefusal(response.status, target));
      failure.http = {
        status: response.status,
        method: input.method.toUpperCase(),
        url: input.url,
        bodyText: await response.text(),
        reason: response.statusText,
        redirectedTo: target ?? "",
      };
      throw failure;
    }
    return response;
  };
}

function isUnderBase(url: string, baseUrl: string): boolean {
  try {
    const u = new URL(url);
    const base = new URL(baseUrl);
    const basePath = base.pathname.replace(/\/+$/, "");
    return u.origin === base.origin && (u.pathname === basePath || u.pathname.startsWith(`${basePath}/`));
  } catch {
    return false;
  }
}
