/** Title-case a string: "blue mountain" → "Blue Mountain", "HUILA" → "Huila". */
export const titleCase = (s: string): string =>
  s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());

/** Format a product price in its own currency: (189, "NOK") → "NOK 189",
 *  (32, "USD") → "$32", (1200, "JPY") → "¥1,200".
 *
 *  Prices are scraped from each roaster's storefront in that store's local
 *  currency, so a bare "$" prefix mislabels every non-US listing. A null
 *  currency (scrape data predating currency capture that no ingest fallback
 *  could resolve) keeps the historical "$" prefix — those rows are
 *  overwhelmingly US stores, and inventing a different display would be no
 *  more accurate. */
export function formatPrice(
  price: number | null | undefined,
  currency?: string | null,
): string | null {
  if (price === null || price === undefined) return null;
  if (currency) {
    try {
      return new Intl.NumberFormat("en", {
        style: "currency",
        currency,
        // Storefront prices are display prices: whole amounts drop the ".00"
        // noise ("$18"), sub-unit amounts keep both digits ("$18.50").
        minimumFractionDigits: Number.isInteger(price) ? 0 : 2,
        maximumFractionDigits: 2,
      }).format(price);
    } catch {
      // Invalid code slipped through ingest — fall through to the default.
    }
  }
  return `$${price}`;
}
