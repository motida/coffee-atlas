import { ImageResponse } from "next/og";

import { COFFEE_MARK_DATA_URI } from "./brand";

export const alt = "Coffee Atlas — a geospatial coffee knowledge graph";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "linear-gradient(135deg, #fdf8f0 0%, #f2d8b0 100%)",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "28px" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={COFFEE_MARK_DATA_URI} width={132} height={132} alt="" />
          <div
            style={{
              fontSize: 96,
              fontWeight: 800,
              color: "#65381d",
              letterSpacing: "-2px",
            }}
          >
            Coffee Atlas
          </div>
        </div>
        <div
          style={{
            fontSize: 40,
            color: "#7a4320",
            marginTop: 36,
            maxWidth: 920,
            lineHeight: 1.3,
          }}
        >
          Mapping the global coffee ecosystem — from bean genetics and farm
          origins to roasting science, distribution, and specialty shops.
        </div>
        <div
          style={{
            fontSize: 26,
            color: "#b86a22",
            marginTop: 44,
            fontWeight: 600,
            letterSpacing: "2px",
          }}
        >
          VARIETIES · ORIGINS · ROASTING · FLAVOR · SHOPS
        </div>
      </div>
    ),
    size,
  );
}
