// Tests for the shared API client: query-string building (via the public
// functions), error propagation, 204 handling, and cookie forwarding.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "./api";

function okResponse(body: unknown = [], status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "",
    json: () => Promise.resolve(body),
  } as Response;
}

const makeFetchMock = () =>
  vi.fn((_input: string, _init?: RequestInit) => Promise.resolve(okResponse()));

let fetchMock = makeFetchMock();

beforeEach(() => {
  fetchMock = makeFetchMock();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function requestedUrl(): string {
  return fetchMock.mock.calls[0][0];
}

describe("query-string building", () => {
  it("serializes scalar params and drops undefined ones", async () => {
    await api.getVarieties(30, 10);
    expect(requestedUrl()).toBe("/api/v1/varieties?limit=30&offset=10");
  });

  it("includes optional params when provided", async () => {
    await api.getVarieties(20, 0, "Arabica");
    expect(requestedUrl()).toBe("/api/v1/varieties?limit=20&offset=0&species=Arabica");
  });

  it("appends one entry per array value", async () => {
    await api.searchText("floral", 20, ["variety", "flavor"]);
    const url = new URL(requestedUrl(), "http://x");
    expect(url.searchParams.getAll("entity_types")).toEqual(["variety", "flavor"]);
    expect(url.searchParams.get("query")).toBe("floral");
  });

  it("omits null-valued params entirely", async () => {
    await api.searchText("floral", 20, undefined, undefined);
    const url = new URL(requestedUrl(), "http://x");
    expect(url.searchParams.has("entity_types")).toBe(false);
    expect(url.searchParams.has("species")).toBe(false);
  });

  it("joins bbox tuples into one comma-separated param", async () => {
    await api.getShopsGeo([139.55, 35.55, 139.9, 35.8], 100);
    const url = new URL(requestedUrl(), "http://x");
    expect(url.searchParams.get("bbox")).toBe("139.55,35.55,139.9,35.8");
  });
});

describe("fetchAPI behavior", () => {
  it("sends the session cookie on every request", async () => {
    await api.getVarieties();
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("include");
  });

  it("throws with the HTTP status on non-2xx", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: "Not Found",
    } as Response);
    await expect(api.getVariety("nope")).rejects.toThrow(/404/);
  });

  it("resolves undefined for 204 No Content", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 204,
      statusText: "No Content",
    } as Response);
    await expect(api.logout()).resolves.toBeUndefined();
  });
});
