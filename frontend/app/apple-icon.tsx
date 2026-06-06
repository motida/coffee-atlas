import { ImageResponse } from "next/og";

import { COFFEE_MARK_DATA_URI } from "./brand";

export const size = { width: 180, height: 180 };
export const contentType = "image/png";

// Safari ignores SVG apple-touch-icons, so render the shared mark to a PNG.
export default function AppleIcon() {
  return new ImageResponse(
    (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={COFFEE_MARK_DATA_URI} width={180} height={180} alt="" />
    ),
    size,
  );
}
