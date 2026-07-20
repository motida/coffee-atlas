// @vitest-environment node
import { describe, expect, it } from "vitest";
import { formatPrice, titleCase } from "./text";

describe("titleCase", () => {
  it("capitalizes each word", () => {
    expect(titleCase("blue mountain")).toBe("Blue Mountain");
    expect(titleCase("HUILA")).toBe("Huila");
  });
});

describe("formatPrice", () => {
  it("formats in the product's own currency", () => {
    expect(formatPrice(32, "USD")).toBe("$32");
    // Intl separates a code-style symbol from the amount with U+00A0.
    expect(formatPrice(189, "NOK")).toBe("NOK\u00A0189");
    expect(formatPrice(1200, "JPY")).toBe("¥1,200");
    expect(formatPrice(21.5, "GBP")).toBe("£21.50");
  });

  it("keeps sub-unit amounts but drops '.00' noise", () => {
    expect(formatPrice(18.5, "USD")).toBe("$18.50");
    expect(formatPrice(18, "USD")).toBe("$18");
  });

  it("falls back to the historical $ prefix when currency is unknown", () => {
    expect(formatPrice(32, null)).toBe("$32");
    expect(formatPrice(32)).toBe("$32");
    // Invalid code that slipped through ingest → same fallback, no crash.
    expect(formatPrice(32, "COFFEE")).toBe("$32");
  });

  it("returns null for a missing price", () => {
    expect(formatPrice(null, "USD")).toBeNull();
    expect(formatPrice(undefined)).toBeNull();
  });
});
