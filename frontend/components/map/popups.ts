import type {
  CountryGeoProperties,
  RegionGeoProperties,
  ShopGeoProperties,
  TradeRouteGeoProperties,
} from "@/lib/types";

/** The data backing a map popup, independent of where on the map it's anchored. */
export interface PopupState {
  longitude: number;
  latitude: number;
  title: string;
  subtitle?: string;
  link?: string;
  detailHref?: string;
  links?: { label: string; href: string }[];
}

export function tradeRoutePopup(
  props: TradeRouteGeoProperties,
  lng: number,
  lat: number,
): PopupState {
  return {
    longitude: lng,
    latitude: lat,
    title: `${props.exporter_name} → ${props.importer_name}`,
    subtitle:
      props.annual_volume != null
        ? `${props.annual_volume.toLocaleString()} t${props.year ? ` (${props.year})` : ""}`
        : "green-coffee trade route",
    links: [
      { label: props.exporter_name, href: `/explore/countries/${props.exporter_id}` },
      { label: props.importer_name, href: `/explore/countries/${props.importer_id}` },
    ],
  };
}

export function shopPopup(props: ShopGeoProperties, lng: number, lat: number): PopupState {
  return {
    longitude: lng,
    latitude: lat,
    title: props.name,
    subtitle: [props.city, props.country].filter(Boolean).join(", ") || undefined,
    link: props.website ?? undefined,
    detailHref: `/explore/shops/${props.id}`,
  };
}

export function countryPopup(props: CountryGeoProperties, lng: number, lat: number): PopupState {
  return {
    longitude: lng,
    latitude: lat,
    title: props.name,
    subtitle: props.iso_code ?? undefined,
    detailHref: `/explore/countries/${props.id}`,
  };
}

export function regionPopup(props: RegionGeoProperties, lng: number, lat: number): PopupState {
  return {
    longitude: lng,
    latitude: lat,
    title: props.name.replace(/\b\w/g, (c) => c.toUpperCase()),
    subtitle: props.country_name,
    detailHref: `/explore/regions/${props.id}`,
  };
}
