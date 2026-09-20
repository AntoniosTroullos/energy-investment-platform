import json
from urllib import error, parse, request

from .models import (
    ClimateAssetResponse,
    ClimateCurrentConditions,
    ClimateEfficiencyEstimate,
)


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def get_asset_climate(latitude: float, longitude: float, technology: str) -> ClimateAssetResponse:
    payload = fetch_open_meteo_current_conditions(latitude, longitude)
    current_payload = payload.get("current", {})

    current_conditions = ClimateCurrentConditions(
        time=current_payload.get("time", ""),
        temperatureC=to_float(current_payload.get("temperature_2m")),
        cloudCoverPct=to_float(current_payload.get("cloud_cover")),
        windSpeed10mKph=to_float(current_payload.get("wind_speed_10m")),
        windSpeed100mKph=to_float(current_payload.get("wind_speed_100m")),
        shortwaveRadiationWm2=to_float(current_payload.get("shortwave_radiation")),
        directNormalIrradianceWm2=to_float(
            current_payload.get("direct_normal_irradiance")
        ),
    )

    return ClimateAssetResponse(
        source="Open-Meteo Forecast API",
        latitude=latitude,
        longitude=longitude,
        assetTechnology=technology or "Unknown",
        current=current_conditions,
        efficiency=estimate_renewable_efficiency(technology, current_conditions),
    )


def fetch_open_meteo_current_conditions(latitude: float, longitude: float) -> dict:
    query_params = parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "cloud_cover",
                    "wind_speed_10m",
                    "wind_speed_100m",
                    "shortwave_radiation",
                    "direct_normal_irradiance",
                ]
            ),
            "timezone": "auto",
        }
    )
    url = f"{OPEN_METEO_FORECAST_URL}?{query_params}"

    http_request = request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "energy-investment-platform/0.1",
        },
    )

    try:
        with request.urlopen(http_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as request_error:
        raise RuntimeError(
            f"Climate API request failed ({request_error.code})."
        ) from request_error
    except error.URLError as request_error:
        raise RuntimeError("Could not reach climate data service.") from request_error
    except json.JSONDecodeError as request_error:
        raise RuntimeError("Climate data service returned invalid JSON.") from request_error


def estimate_renewable_efficiency(
    technology: str,
    current: ClimateCurrentConditions,
) -> ClimateEfficiencyEstimate:
    modeled_technology = normalize_modeled_technology(technology)

    if modeled_technology == "solar":
        score = estimate_solar_efficiency(current)
        return ClimateEfficiencyEstimate(
            modeledTechnology="solar",
            estimatedEfficiencyPct=score,
            band=get_efficiency_band(score),
            summary=build_solar_summary(score, current),
        )

    if modeled_technology in {"wind", "offshore_wind"}:
        score = estimate_wind_efficiency(current, modeled_technology == "offshore_wind")
        return ClimateEfficiencyEstimate(
            modeledTechnology=modeled_technology,
            estimatedEfficiencyPct=score,
            band=get_efficiency_band(score),
            summary=build_wind_summary(score, current, modeled_technology),
        )

    return ClimateEfficiencyEstimate(
        modeledTechnology="unsupported",
        estimatedEfficiencyPct=None,
        band="Not modeled",
        summary=(
            "This first climate pass estimates current efficiency for solar and wind "
            "plants only."
        ),
    )


def normalize_modeled_technology(technology: str) -> str:
    normalized = technology.strip().lower()

    if "offshore" in normalized and "wind" in normalized:
        return "offshore_wind"

    if "solar" in normalized or "pv" in normalized:
        return "solar"

    if "wind" in normalized:
        return "wind"

    return "unsupported"


def estimate_solar_efficiency(current: ClimateCurrentConditions) -> float:
    shortwave_radiation = current.shortwaveRadiationWm2 or 0
    direct_normal_irradiance = current.directNormalIrradianceWm2 or shortwave_radiation
    cloud_cover = current.cloudCoverPct or 0
    temperature = current.temperatureC or 25

    # This is a simple operational indicator, not a full PV performance model.
    irradiance_score = min((0.55 * shortwave_radiation) + (0.45 * direct_normal_irradiance), 900) / 9
    cloud_penalty = cloud_cover * 0.18
    temperature_penalty = max(temperature - 25, 0) * 1.2

    return clamp(round(irradiance_score - cloud_penalty - temperature_penalty, 1), 0, 100)


def estimate_wind_efficiency(
    current: ClimateCurrentConditions,
    is_offshore: bool,
) -> float:
    wind_speed = current.windSpeed100mKph or current.windSpeed10mKph or 0

    # This rough curve mirrors the idea of a turbine power curve in a readable way.
    if wind_speed < 12:
        score = 0
    elif wind_speed < 20:
        score = 25 + ((wind_speed - 12) / 8) * 20
    elif wind_speed < 30:
        score = 45 + ((wind_speed - 20) / 10) * 30
    elif wind_speed < 45:
        score = 75 + ((wind_speed - 30) / 15) * 20
    elif wind_speed <= 90:
        score = 95
    else:
        score = 20

    if is_offshore:
        score += 5

    return clamp(round(score, 1), 0, 100)


def build_solar_summary(score: float, current: ClimateCurrentConditions) -> str:
    if score >= 75:
        return "Strong solar conditions right now, with good irradiance support for PV output."

    if score >= 45:
        return "Moderate solar conditions right now. Irradiance is usable, but cloud or heat is reducing performance."

    return "Weak solar conditions right now. Low irradiance or heavy cloud is limiting expected PV performance."


def build_wind_summary(
    score: float,
    current: ClimateCurrentConditions,
    modeled_technology: str,
) -> str:
    technology_label = "offshore wind" if modeled_technology == "offshore_wind" else "wind"

    if score >= 75:
        return f"Strong {technology_label} conditions right now, with supportive wind speeds for generation."

    if score >= 45:
        return f"Moderate {technology_label} conditions right now. Wind speeds are usable but not especially strong."

    return f"Weak {technology_label} conditions right now. Wind speeds are too low, or high enough to be operationally limiting."


def get_efficiency_band(score: float | None) -> str:
    if score is None:
        return "Not modeled"

    if score >= 75:
        return "High"

    if score >= 45:
        return "Moderate"

    return "Low"


def to_float(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)

    return None


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))
