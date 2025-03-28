import createClient from "openapi-fetch";

import { type GalaxyApiPaths } from "./schema/index.js";


function apiClientFactory(baseUrl?: string) {
    return createClient<GalaxyApiPaths>({ baseUrl: baseUrl ?? "https://usegalaxy.org" });
}

export type GalaxyApiClient = ReturnType<typeof apiClientFactory>;

let client: GalaxyApiClient;

/**
 * Returns the Galaxy API client.
 *
 * It can be used to make requests to the Galaxy API using the OpenAPI schema.
 *
 * See: https://openapi-ts.dev/openapi-fetch/
 */
export function GalaxyApi(): GalaxyApiClient {
    if (!client) {
        client = apiClientFactory();
    }

    return client;
}
