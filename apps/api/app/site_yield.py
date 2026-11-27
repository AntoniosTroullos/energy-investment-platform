"""What a solar or wind plant at one site would actually have produced.

What was here before
--------------------
`app/climate.py` read Open-Meteo's CURRENT conditions and turned them into a
0-100 "efficiency" score built from invented coefficients -- a cloud penalty of
0.18 per percent, a temperature penalty of 1.2 per degree, a wind curve made of
four straight lines. It reads like physics and is not: the numbers have no
source, the output has no unit, and a single instant says nothing about yield
anyway. A site is an investment because of what it produces over time.

What this does instead
----------------------
Hourly weather over a real window (several days back and the forecast forward),
through two standard, cited engineering models, producing per-unit output --
MW per MW installed, every hour -- and from it a capacity factor with a unit
and a meaning.

Solar (PVWatts-style, NREL):
    cell temperature  T_cell = T_air + (NOCT - 20) / 800 * POA
    DC output         P_dc   = POA / 1000 * (1 + gamma * (T_cell - 25))
    AC output         P_ac   = min(P_dc * (1 - system_losses), 1.0)
POA is Open-Meteo's own global tilted irradiance for a fixed array at
`DEFAULT_TILT_DEGREES` facing the equator, so the plane-of-array transposition
is done by the weather service rather than approximated here. The temperature
coefficient and the loss stack are crystalline-silicon defaults.

Wind (power curve with air-density correction):
    rho    = p / (R_specific * T)                      ideal gas, dry air
    v_eq   = v * (rho / 1.225) ** (1/3)                density-corrected speed
    P/P_r  = 0 below cut-in, (v^3 - vin^3)/(vr^3 - vin^3) up to rated,
             1 to cut-out, 0 above
then a wake-and-availability loss. The cubic ramp is the physical one (power in
the wind goes as the cube of speed); a manufacturer's measured curve would be
better and is not public for a generic site.

Both models are explicit about being generic: a real project uses the actual
module, inverter and turbine. What they give that the old score could not is a
number with a unit, derived from published formulas, over a stated window.

The capture price
-----------------
When the live day-ahead curve overlaps the weather window, the site's own
hourly output is weighted against real prices to give that site's capture price
in the real market -- the same quantity the solved scenarios report per region,
but computed from this site's own weather. That is as close as this platform
gets to "what would this specific project have earned last week".
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib import error, parse, request

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Fixed-tilt array facing the equator. Near the optimum for Greek latitudes and
# the common choice for utility-scale fixed-tilt plants here.
DEFAULT_TILT_DEGREES = 30
DEFAULT_AZIMUTH_DEGREES = 0  # Open-Meteo: 0 is south.

DEFAULT_PAST_DAYS = 5
DEFAULT_FORECAST_DAYS = 2

# --- Solar model constants (crystalline silicon, PVWatts defaults) ---------
NOCT_CELSIUS = 45.0
TEMPERATURE_COEFFICIENT_PER_C = -0.0034
STANDARD_TEST_TEMPERATURE_C = 25.0
STANDARD_IRRADIANCE_W_M2 = 1000.0
# Soiling, wiring, mismatch, inverter and availability losses combined.
SOLAR_SYSTEM_LOSS_FRACTION = 0.14

# DC array capacity divided by inverter (AC) capacity. A plant is permitted,
# connected and settled on its AC rating, so that is the capacity this module
# reports output "per unit" of; the array behind it is deliberately larger.
#
# 1.0 means no oversizing and is the library default, because it is the one
# value that asserts nothing about how a project was designed. Greek
# utility-scale plants are routinely built at 1.2-1.3: modules are the
# cheapest part of the system, and an oversized array fills the shoulders of
# the day at the cost of clipping a few midday hours.
NO_OVERSIZING = 1.0
DEFAULT_DC_AC_RATIO = 1.25

# Share of solar capex that scales with the DC array rather than the AC side.
# Modules are the bulk of it; inverters, grid connection, land, civil works and
# development scale with AC capacity or are fixed. Roughly 40% is the usual
# benchmark range for utility-scale PV, and it is approximate -- its only job
# is to stop oversizing from looking free, which it is not. A user with a real
# quote should set capex directly instead of relying on it.
MODULE_SHARE_OF_SOLAR_CAPEX = 0.40

# --- Wind model constants (generic IEC Class II onshore turbine) -----------
CUT_IN_MS = 3.0
RATED_MS = 11.5
CUT_OUT_MS = 25.0
# Wake losses within an array plus turbine availability.
WIND_LOSS_FRACTION = 0.12
DRY_AIR_GAS_CONSTANT = 287.05
STANDARD_AIR_DENSITY = 1.225

KMH_TO_MS = 1 / 3.6


@dataclass(frozen=True)
class SiteYield:
    carrier: str
    timestamps: list[str]
    output_per_unit: list[float]
    capacity_factor_pct: float
    peak_output_per_unit: float
    producing_hours: int
    window_hours: int
    model: str
    assumptions: str
    # Solar only: the array's oversizing and what the inverter clipped off.
    dc_ac_ratio: float | None = None
    clipped_pct_of_dc: float | None = None
    hours_clipped: int | None = None


def get_site_yield(
    latitude: float,
    longitude: float,
    carrier: str,
    *,
    past_days: int = DEFAULT_PAST_DAYS,
    forecast_days: int = DEFAULT_FORECAST_DAYS,
    dc_ac_ratio: float = DEFAULT_DC_AC_RATIO,
) -> SiteYield | None:
    """Per-hour output for one site, or None for a carrier this does not model
    or when the weather service cannot be reached."""
    if carrier not in ("solar", "wind"):
        return None

    try:
        weather = fetch_hourly_weather(latitude, longitude, past_days, forecast_days)
    except RuntimeError:
        return None

    hourly = weather.get("hourly") or {}
    timestamps = [str(stamp) for stamp in hourly.get("time") or []]
    if not timestamps:
        return None

    clipped_pct: float | None = None
    clipped_hours: int | None = None
    ratio: float | None = None

    if carrier == "solar":
        ratio = dc_ac_ratio
        unclipped = solar_dc_per_unit_of_ac(
            _floats(hourly.get("global_tilted_irradiance"), len(timestamps)),
            _floats(hourly.get("temperature_2m"), len(timestamps)),
            dc_ac_ratio,
        )
        output = [min(value, 1.0) for value in unclipped]
        lost, clipped_hours = clipping_losses(unclipped)
        available = sum(unclipped)
        clipped_pct = round(100.0 * lost / available, 2) if available > 0 else 0.0
        model = (
            f"PVWatts-style fixed-tilt array at {DEFAULT_TILT_DEGREES} degrees facing south, "
            f"DC/AC {dc_ac_ratio:.2f} clipped at the inverter, on Open-Meteo plane-of-array irradiance"
        )
        assumptions = (
            f"Temperature coefficient {TEMPERATURE_COEFFICIENT_PER_C * 100:.2f} %/C with an NOCT cell model "
            f"({NOCT_CELSIUS:.0f} C), {SOLAR_SYSTEM_LOSS_FRACTION * 100:.0f}% system losses (soiling, wiring, "
            f"mismatch, inverter, availability), and a DC array {dc_ac_ratio:.2f} times the AC rating with "
            "output clipped at it. Per-unit values are per unit of AC capacity, which is what a plant is "
            "connected and settled on. Generic crystalline-silicon defaults, not a specific module."
        )
    else:
        output = wind_output_per_unit(
            _floats(hourly.get("wind_speed_100m"), len(timestamps)),
            _floats(hourly.get("temperature_2m"), len(timestamps)),
            _floats(hourly.get("surface_pressure"), len(timestamps)),
        )
        model = "Generic IEC Class II power curve at 100 m, air-density corrected"
        assumptions = (
            f"Cut-in {CUT_IN_MS:.0f} m/s, rated {RATED_MS:.1f} m/s, cut-out {CUT_OUT_MS:.0f} m/s with a cubic "
            f"ramp, {WIND_LOSS_FRACTION * 100:.0f}% wake and availability losses, density from the ideal gas law. "
            "A generic curve, not a specific turbine, and hub height is fixed at the 100 m wind the "
            "weather model provides."
        )

    producing = sum(1 for value in output if value > 0.001)
    return SiteYield(
        carrier=carrier,
        timestamps=timestamps,
        output_per_unit=[round(value, 4) for value in output],
        capacity_factor_pct=round(100.0 * sum(output) / len(output), 2) if output else 0.0,
        peak_output_per_unit=round(max(output), 4) if output else 0.0,
        producing_hours=producing,
        window_hours=len(output),
        model=model,
        assumptions=assumptions,
        dc_ac_ratio=ratio,
        clipped_pct_of_dc=clipped_pct,
        hours_clipped=clipped_hours,
    )


# ---------------------------------------------------------------------------
# The models
# ---------------------------------------------------------------------------


def solar_dc_per_unit_of_ac(
    poa_w_m2: list[float],
    air_temperature_c: list[float],
    dc_ac_ratio: float = NO_OVERSIZING,
) -> list[float]:
    """What the array produces each hour, per unit of the plant's AC rating,
    BEFORE the inverter clips it.

    Returned unclipped on purpose. Degradation acts on the DC array, so a
    lifetime simulation has to fade this series and clip afterwards -- clipping
    first and fading the result would understate later years, because a
    degraded oversized array still reaches the inverter limit at midday. That
    ordering is the reason oversizing slows a plant's apparent AC degradation,
    and it only shows up if the two steps happen in the right order.

    Values above 1.0 are the hours that will be clipped."""
    ratio = max(dc_ac_ratio, 0.0)
    output: list[float] = []
    for poa, air_temperature in zip(poa_w_m2, air_temperature_c):
        if poa <= 0:
            output.append(0.0)
            continue
        cell_temperature = air_temperature + (NOCT_CELSIUS - 20.0) / 800.0 * poa
        dc = (poa / STANDARD_IRRADIANCE_W_M2) * (
            1 + TEMPERATURE_COEFFICIENT_PER_C * (cell_temperature - STANDARD_TEST_TEMPERATURE_C)
        )
        output.append(max(0.0, dc * (1 - SOLAR_SYSTEM_LOSS_FRACTION) * ratio))
    return output


def solar_output_per_unit(
    poa_w_m2: list[float],
    air_temperature_c: list[float],
    dc_ac_ratio: float = NO_OVERSIZING,
) -> list[float]:
    """Hourly AC output per unit of the plant's AC rating, clipped at the
    inverter. At a ratio of 1.0 this is the plain PVWatts result."""
    return [min(value, 1.0) for value in solar_dc_per_unit_of_ac(poa_w_m2, air_temperature_c, dc_ac_ratio)]


def clipping_losses(dc_per_unit_of_ac: list[float]) -> tuple[float, int]:
    """Energy lost to the inverter limit, in per-unit hours, and how many hours
    were clipped. Worth reporting rather than absorbing: clipping is the cost
    side of oversizing, and a plant whose design is right loses a few percent
    of a much larger harvest."""
    lost = 0.0
    hours = 0
    for value in dc_per_unit_of_ac:
        if value > 1.0:
            lost += value - 1.0
            hours += 1
    return lost, hours


def solar_capex_multiplier(dc_ac_ratio: float) -> float:
    """How much a given DC/AC ratio raises cost per kW of AC capacity.

    Without this, sliding the ratio up would raise output and IRR at no cost,
    which is a free lunch the real world does not offer. Only the module-side
    share of capex scales with the array; the rest follows the AC rating."""
    ratio = max(dc_ac_ratio, 0.0)
    return (1 - MODULE_SHARE_OF_SOLAR_CAPEX) + MODULE_SHARE_OF_SOLAR_CAPEX * ratio


def air_density(temperature_c: float, pressure_hpa: float) -> float:
    kelvin = temperature_c + 273.15
    if kelvin <= 0 or pressure_hpa <= 0:
        return STANDARD_AIR_DENSITY
    return (pressure_hpa * 100.0) / (DRY_AIR_GAS_CONSTANT * kelvin)


def wind_output_per_unit(
    speed_kmh: list[float],
    air_temperature_c: list[float],
    pressure_hpa: list[float],
) -> list[float]:
    output: list[float] = []
    for speed, temperature, pressure in zip(speed_kmh, air_temperature_c, pressure_hpa):
        metres_per_second = speed * KMH_TO_MS
        density = air_density(temperature, pressure)
        # Power scales with density, and with the cube of speed, so correcting
        # the SPEED by the cube root of the density ratio is equivalent to
        # correcting the power -- and keeps cut-in and cut-out meaningful.
        equivalent = metres_per_second * (density / STANDARD_AIR_DENSITY) ** (1.0 / 3.0)
        output.append(power_curve(equivalent) * (1 - WIND_LOSS_FRACTION))
    return output


def power_curve(speed_ms: float) -> float:
    if speed_ms < CUT_IN_MS or speed_ms >= CUT_OUT_MS:
        return 0.0
    if speed_ms >= RATED_MS:
        return 1.0
    return (speed_ms**3 - CUT_IN_MS**3) / (RATED_MS**3 - CUT_IN_MS**3)


# ---------------------------------------------------------------------------
# Weather
# ---------------------------------------------------------------------------


def fetch_hourly_weather(latitude: float, longitude: float, past_days: int, forecast_days: int) -> dict:
    query = parse.urlencode(
        {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(
                ["global_tilted_irradiance", "temperature_2m", "wind_speed_100m", "surface_pressure"]
            ),
            "tilt": DEFAULT_TILT_DEGREES,
            "azimuth": DEFAULT_AZIMUTH_DEGREES,
            "past_days": past_days,
            "forecast_days": forecast_days,
            # UTC throughout, so these hours can be matched to day-ahead prices
            # without a second timezone conversion.
            "timezone": "UTC",
        }
    )
    http_request = request.Request(
        f"{OPEN_METEO_FORECAST_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "energy-investment-platform/0.1"},
    )
    try:
        with request.urlopen(http_request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as request_error:
        raise RuntimeError(f"Climate API request failed ({request_error.code}).") from request_error
    except (error.URLError, TimeoutError) as request_error:
        raise RuntimeError("Could not reach climate data service.") from request_error
    except json.JSONDecodeError as request_error:
        raise RuntimeError("Climate data service returned invalid JSON.") from request_error


def _floats(values: list | None, length: int) -> list[float]:
    """Open-Meteo returns null for an hour it has no value for; those become
    zero, which for irradiance and wind means "no production in that hour" --
    the conservative reading."""
    source = values or []
    return [float(value) if isinstance(value, (int, float)) else 0.0 for value in source[:length]] + [0.0] * max(
        0, length - len(source)
    )
