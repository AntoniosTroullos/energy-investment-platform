import type { AssetSelection } from "../types/asset";

export function getVoltageOptions(assets: AssetSelection[]) {
  const values = [...new Set(
    assets
      .map((asset) => normalizeVoltageValue(asset.properties.voltage_kv))
      .filter((value): value is string => value !== null),
  )].sort((left, right) => Number(right) - Number(left));

  const options = values.map((value) => ({
    value,
    label: `${value} kV`,
  }));

  const hasUnknown = assets.some(
    (asset) => normalizeVoltageValue(asset.properties.voltage_kv) === null,
  );

  if (hasUnknown) {
    options.push({
      value: "unknown",
      label: "Unknown voltage",
    });
  }

  return options;
}

export function filterAssetsByVoltage(assets: AssetSelection[], voltageFilter: string) {
  if (voltageFilter === "all") {
    return assets;
  }

  return assets.filter((asset) => matchesVoltageFilter(asset, voltageFilter));
}

export function matchesVoltageFilter(asset: AssetSelection, voltageFilter: string) {
  if (voltageFilter === "all") {
    return true;
  }

  const voltageValue = normalizeVoltageValue(asset.properties.voltage_kv);

  if (voltageFilter === "unknown") {
    return voltageValue === null;
  }

  return voltageValue === voltageFilter;
}

// No real line/substation in this dataset exceeds 500 kV. A few upstream
// records carry a voltage_kv far above that (e.g. 400000150, 15400034) —
// confirmed against the live backend to be multiple OSM circuit voltages
// (in volts, semicolon-separated, such as "400000;150000") concatenated
// without their separator before the volts-to-kV conversion. Since the
// original values can't be reliably recovered here, treat anything above
// this ceiling as unknown rather than surface it as a bogus filter option.
const MAX_PLAUSIBLE_VOLTAGE_KV = 800;

export function normalizeVoltageValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return isPlausibleVoltageKv(value) ? String(value) : null;
  }

  if (typeof value === "string") {
    const trimmedValue = value.trim();
    if (trimmedValue.length === 0) {
      return null;
    }

    const primaryValue = trimmedValue.split(/[;,/]/)[0]?.trim();
    if (!primaryValue || primaryValue.length === 0) {
      return null;
    }

    const numericPrimaryValue = Number(primaryValue);
    if (Number.isFinite(numericPrimaryValue) && !isPlausibleVoltageKv(numericPrimaryValue)) {
      return null;
    }

    return primaryValue;
  }

  return null;
}

function isPlausibleVoltageKv(value: number) {
  return value > 0 && value <= MAX_PLAUSIBLE_VOLTAGE_KV;
}

export function getVoltageDisplayValue(value: unknown) {
  const normalizedValue = normalizeVoltageValue(value);
  return normalizedValue ? `${normalizedValue} kV` : "Unknown voltage";
}
