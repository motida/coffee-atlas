/** Title-case a string: "blue mountain" → "Blue Mountain", "HUILA" → "Huila". */
export const titleCase = (s: string): string =>
  s.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
