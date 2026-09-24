import math

import streamlit as st
from CoolProp.CoolProp import PropsSI


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="HX UA Calculator",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 Heat Exchanger UA Calculator")

st.caption(
    "CoolProp thermodynamic properties · Nine equal-duty WTD "
    "segments · Pressures entered as absolute bar(a)"
)


# ============================================================
# FLUID DATABASE
# ============================================================

FLUIDS = {
    "Water": "Water",
    "Typical natural gas": (
        "HEOS::Methane[0.90]"
        "&Ethane[0.05]"
        "&Propane[0.02]"
        "&Nitrogen[0.02]"
        "&CarbonDioxide[0.01]"
    ),
    "Carbon dioxide": "CO2",
    "Methane": "Methane",
    "Ethane": "Ethane",
    "Propane": "Propane",
    "Butane": "n-Butane",
    "Nitrogen": "Nitrogen",
    "Oxygen": "Oxygen",
    "Hydrogen": "Hydrogen",
    "Air": "Air",
    "Ammonia": "Ammonia",
    "R134a": "R134a",
    "R1234yf": "R1234yf",
    "Methanol": "Methanol",
    "Ethanol": "Ethanol",
}

NATURAL_GAS_COMPOSITION = {
    "Methane": 90.0,
    "Ethane": 5.0,
    "Propane": 2.0,
    "Nitrogen": 2.0,
    "Carbon dioxide": 1.0,
}

FLOW_UNITS = {
    "kg/s": 1.0,
    "kg/h": 1.0 / 3600.0,
    "t/h": 1000.0 / 3600.0,
}

NUMBER_OF_SEGMENTS = 9


# ============================================================
# BASIC CONVERSIONS
# ============================================================

def parse_optional_number(value):
    """
    Convert a text field to float.
    Empty text returns None.
    """
    cleaned = str(value).strip()

    if cleaned == "":
        return None

    return float(cleaned.replace(",", "."))


def mass_flow_to_kg_s(value, unit):
    return value * FLOW_UNITS[unit]


def mass_flow_from_kg_s(value, unit):
    return value / FLOW_UNITS[unit]


def temperature_c_to_k(temperature_c):
    temperature_k = temperature_c + 273.15

    if temperature_k <= 0:
        raise ValueError(
            "Temperature must be above absolute zero."
        )

    return temperature_k


def pressure_bar_to_pa(pressure_bara):
    if pressure_bara <= 0:
        raise ValueError(
            "Absolute pressure must be greater than zero."
        )

    return pressure_bara * 100_000.0


# ============================================================
# COOLPROP FUNCTIONS
# ============================================================

@st.cache_data(show_spinner=False)
def enthalpy_kj_kg(fluid, temperature_c, pressure_bara):
    """
    Specific enthalpy in kJ/kg.
    """
    result = PropsSI(
        "Hmass",
        "T",
        temperature_c_to_k(temperature_c),
        "P",
        pressure_bar_to_pa(pressure_bara),
        fluid,
    )

    if not math.isfinite(result):
        raise ValueError(
            "CoolProp returned an invalid enthalpy."
        )

    return result / 1000.0


def temperature_from_enthalpy(
    fluid,
    enthalpy_target_kj_kg,
    pressure_bara,
    suggested_min_c=-200.0,
    suggested_max_c=800.0,
):
    """
    Calculate temperature from enthalpy and pressure.

    A direct CoolProp H-P flash is attempted first.
    A numerical temperature search is used as a fallback,
    particularly for mixtures.
    """
    pressure_pa = pressure_bar_to_pa(pressure_bara)
    enthalpy_target_j_kg = enthalpy_target_kj_kg * 1000.0

    try:
        temperature_k = PropsSI(
            "T",
            "Hmass",
            enthalpy_target_j_kg,
            "P",
            pressure_pa,
            fluid,
        )

        temperature_c = temperature_k - 273.15

        if math.isfinite(temperature_c):
            return temperature_c

    except Exception:
        pass

    # Fallback search for mixtures or unsupported H-P flashes
    lower_limit = max(-272.0, suggested_min_c)
    upper_limit = suggested_max_c

    valid_points = []
    number_of_scan_points = 500

    for index in range(number_of_scan_points + 1):
        fraction = index / number_of_scan_points

        temperature_c = (
            lower_limit
            + fraction * (upper_limit - lower_limit)
        )

        try:
            calculated_h = enthalpy_kj_kg(
                fluid,
                temperature_c,
                pressure_bara,
            )

            difference = (
                calculated_h - enthalpy_target_kj_kg
            )

            if math.isfinite(difference):
                valid_points.append(
                    (temperature_c, difference)
                )

        except Exception:
            continue

    for index in range(len(valid_points) - 1):
        t_low, f_low = valid_points[index]
        t_high, f_high = valid_points[index + 1]

        if abs(f_low) < 1e-9:
            return t_low

        if f_low * f_high <= 0:
            for _ in range(80):
                t_middle = (t_low + t_high) / 2.0

                h_middle = enthalpy_kj_kg(
                    fluid,
                    t_middle,
                    pressure_bara,
                )

                f_middle = (
                    h_middle - enthalpy_target_kj_kg
                )

                if abs(f_middle) < 1e-8:
                    return t_middle

                if f_low * f_middle <= 0:
                    t_high = t_middle
                    f_high = f_middle
                else:
                    t_low = t_middle
                    f_low = f_middle

            return (t_low + t_high) / 2.0

    raise ValueError(
        "Could not determine temperature from enthalpy "
        "and pressure. Check the fluid state and CoolProp range."
    )


# ============================================================
# TEMPERATURE-DIFFERENCE FUNCTIONS
# ============================================================

def logarithmic_mean_temperature_difference(dt_1, dt_2):
    """
    LMTD = (dt1 - dt2) / ln(dt1 / dt2)
    """
    if dt_1 <= 0 or dt_2 <= 0:
        raise ValueError(
            "Zero or negative temperature approach detected."
        )

    if math.isclose(
        dt_1,
        dt_2,
        rel_tol=1e-10,
        abs_tol=1e-12,
    ):
        return dt_1

    return (
        (dt_1 - dt_2)
        / math.log(dt_1 / dt_2)
    )


def calculate_wtd(
    hot_temperatures,
    cold_temperatures,
    total_duty_kw,
):
    """
    Reproduces the Excel method:

    dQi = Q / 9
    dLMTDi = (dT1i - dT2i) / ln(dT1i / dT2i)
    dQ/dLMTD = dQi / dLMTDi
    WTD = Q / sum(dQi / dLMTDi)
    """
    duty_per_segment = (
        total_duty_kw / NUMBER_OF_SEGMENTS
    )

    total_dq_over_lmtd = 0.0
    segment_results = []

    for index in range(NUMBER_OF_SEGMENTS):
        delta_t_1 = (
            hot_temperatures[index]
            - cold_temperatures[index]
        )

        delta_t_2 = (
            hot_temperatures[index + 1]
            - cold_temperatures[index + 1]
        )

        segment_lmtd = (
            logarithmic_mean_temperature_difference(
                delta_t_1,
                delta_t_2,
            )
        )

        dq_over_lmtd = (
            duty_per_segment / segment_lmtd
        )

        total_dq_over_lmtd += dq_over_lmtd

        segment_results.append(
            {
                "Segment": index + 1,
                "Hot T1 [°C]": hot_temperatures[index],
                "Cold T1 [°C]": cold_temperatures[index],
                "ΔT1 [K]": delta_t_1,
                "Hot T2 [°C]": hot_temperatures[index + 1],
                "Cold T2 [°C]": cold_temperatures[index + 1],
                "ΔT2 [K]": delta_t_2,
                "dLMTD [K]": segment_lmtd,
                "dQi [kW]": duty_per_segment,
                "dQi/dLMTD [kW/K]": dq_over_lmtd,
            }
        )

    if total_dq_over_lmtd <= 0:
        raise ValueError(
            "The sum of dQi/dLMTD is not positive."
        )

    wtd = total_duty_kw / total_dq_over_lmtd

    return wtd, segment_results


# ============================================================
# STREAM DATA
# ============================================================

def get_stream_data(side):
    """
    Read one stream from Streamlit session state.
    """
    fluid_name = st.session_state[
        f"{side}_fluid_name"
    ]

    flow_value = parse_optional_number(
        st.session_state[f"{side}_flow_text"]
    )

    outlet_temperature = parse_optional_number(
        st.session_state[f"{side}_tout_text"]
    )

    flow_unit = st.session_state[
        f"{side}_flow_unit"
    ]

    return {
        "fluid_name": fluid_name,
        "fluid_code": FLUIDS[fluid_name],
        "flow_value": flow_value,
        "flow_unit": flow_unit,
        "flow_kg_s": (
            None
            if flow_value is None
            else mass_flow_to_kg_s(
                flow_value,
                flow_unit,
            )
        ),
        "temperature_in": st.session_state[
            f"{side}_tin"
        ],
        "temperature_out": outlet_temperature,
        "pressure_in": st.session_state[
            f"{side}_pin"
        ],
        "pressure_out": st.session_state[
            f"{side}_pout"
        ],
    }


def side_input_area(
    title,
    side,
    default_fluid,
    default_flow,
    default_tin,
    default_tout,
    default_pressure,
):
    st.subheader(title)

    fluid_names = list(FLUIDS.keys())

    st.selectbox(
        "Fluid",
        fluid_names,
        index=fluid_names.index(default_fluid),
        key=f"{side}_fluid_name",
    )

    flow_column, unit_column = st.columns(2)

    flow_column.text_input(
        "Mass flow — may be left empty",
        value=default_flow,
        key=f"{side}_flow_text",
    )

    unit_column.selectbox(
        "Flow unit",
        list(FLOW_UNITS.keys()),
        index=1,
        key=f"{side}_flow_unit",
    )

    temperature_in_column, temperature_out_column = (
        st.columns(2)
    )

    temperature_in_column.number_input(
        "Inlet temperature [°C]",
        value=float(default_tin),
        format="%.4f",
        key=f"{side}_tin",
    )

    temperature_out_column.text_input(
        "Outlet temperature [°C] — may be left empty",
        value=default_tout,
        key=f"{side}_tout_text",
    )

    pressure_in_column, pressure_out_column = (
        st.columns(2)
    )

    pressure_in_column.number_input(
        "Inlet pressure [bar(a)]",
        min_value=0.001,
        value=float(default_pressure),
        format="%.4f",
        key=f"{side}_pin",
    )

    pressure_out_column.number_input(
        "Outlet pressure [bar(a)]",
        min_value=0.001,
        value=float(default_pressure),
        format="%.4f",
        key=f"{side}_pout",
    )


# ============================================================
# AUTOMATIC HEAT-BALANCE SOLVER
# ============================================================

def balance_missing_field():
    """
    Fill exactly one missing field:

    - hot mass flow
    - hot outlet temperature
    - cold mass flow
    - cold outlet temperature
    """
    st.session_state["balance_success"] = ""
    st.session_state["balance_error"] = ""

    try:
        hot = get_stream_data("hot")
        cold = get_stream_data("cold")

        missing_fields = []

        if hot["flow_value"] is None:
            missing_fields.append("hot_flow")

        if hot["temperature_out"] is None:
            missing_fields.append("hot_tout")

        if cold["flow_value"] is None:
            missing_fields.append("cold_flow")

        if cold["temperature_out"] is None:
            missing_fields.append("cold_tout")

        if len(missing_fields) == 0:
            raise ValueError(
                "No field is empty. Clear exactly one mass-flow "
                "or outlet-temperature field."
            )

        if len(missing_fields) > 1:
            raise ValueError(
                "More than one balance field is empty. "
                "Leave exactly one field empty."
            )

        missing = missing_fields[0]

        h_hot_in = enthalpy_kj_kg(
            hot["fluid_code"],
            hot["temperature_in"],
            hot["pressure_in"],
        )

        h_cold_in = enthalpy_kj_kg(
            cold["fluid_code"],
            cold["temperature_in"],
            cold["pressure_in"],
        )

        # ----------------------------------------------------
        # Missing hot mass flow
        # ----------------------------------------------------

        if missing == "hot_flow":
            if cold["flow_kg_s"] is None:
                raise ValueError(
                    "Cold-side flow is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["temperature_out"],
                hot["pressure_out"],
            )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["temperature_out"],
                cold["pressure_out"],
            )

            q_cold = (
                cold["flow_kg_s"]
                * (h_cold_out - h_cold_in)
            )

            hot_delta_h = h_hot_in - h_hot_out

            if q_cold <= 0 or hot_delta_h <= 0:
                raise ValueError(
                    "The entered temperatures do not produce "
                    "a positive heat duty."
                )

            solved_flow_kg_s = q_cold / hot_delta_h

            solved_display_flow = mass_flow_from_kg_s(
                solved_flow_kg_s,
                hot["flow_unit"],
            )

            st.session_state["hot_flow_text"] = (
                f"{solved_display_flow:.6f}"
            )

            solved_name = "hot-side mass flow"
            solved_value = (
                f"{solved_display_flow:.6f} "
                f"{hot['flow_unit']}"
            )

        # ----------------------------------------------------
        # Missing cold mass flow
        # ----------------------------------------------------

        elif missing == "cold_flow":
            if hot["flow_kg_s"] is None:
                raise ValueError(
                    "Hot-side flow is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["temperature_out"],
                hot["pressure_out"],
            )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["temperature_out"],
                cold["pressure_out"],
            )

            q_hot = (
                hot["flow_kg_s"]
                * (h_hot_in - h_hot_out)
            )

            cold_delta_h = h_cold_out - h_cold_in

            if q_hot <= 0 or cold_delta_h <= 0:
                raise ValueError(
                    "The entered temperatures do not produce "
                    "a positive heat duty."
                )

            solved_flow_kg_s = q_hot / cold_delta_h

            solved_display_flow = mass_flow_from_kg_s(
                solved_flow_kg_s,
                cold["flow_unit"],
            )

            st.session_state["cold_flow_text"] = (
                f"{solved_display_flow:.6f}"
            )

            solved_name = "cold-side mass flow"
            solved_value = (
                f"{solved_display_flow:.6f} "
                f"{cold['flow_unit']}"
            )

        # ----------------------------------------------------
        # Missing hot outlet temperature
        # ----------------------------------------------------

        elif missing == "hot_tout":
            if hot["flow_kg_s"] is None:
                raise ValueError(
                    "Hot-side flow is required."
                )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["temperature_out"],
                cold["pressure_out"],
            )

            q_cold = (
                cold["flow_kg_s"]
                * (h_cold_out - h_cold_in)
            )

            if q_cold <= 0:
                raise ValueError(
                    "The cold side does not produce "
                    "a positive heat duty."
                )

            target_hot_outlet_h = (
                h_hot_in
                - q_cold / hot["flow_kg_s"]
            )

            solved_temperature = temperature_from_enthalpy(
                hot["fluid_code"],
                target_hot_outlet_h,
                hot["pressure_out"],
                suggested_min_c=-250.0,
                suggested_max_c=hot["temperature_in"] + 300.0,
            )

            if solved_temperature >= hot["temperature_in"]:
                raise ValueError(
                    "The solved hot outlet temperature is not "
                    "below the hot inlet temperature."
                )

            st.session_state["hot_tout_text"] = (
                f"{solved_temperature:.6f}"
            )

            solved_name = "hot-side outlet temperature"
            solved_value = f"{solved_temperature:.6f} °C"

        # ----------------------------------------------------
        # Missing cold outlet temperature
        # ----------------------------------------------------

        else:
            if cold["flow_kg_s"] is None:
                raise ValueError(
                    "Cold-side flow is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["temperature_out"],
                hot["pressure_out"],
            )

            q_hot = (
                hot["flow_kg_s"]
                * (h_hot_in - h_hot_out)
            )

            if q_hot <= 0:
                raise ValueError(
                    "The hot side does not produce "
                    "a positive heat duty."
                )

            target_cold_outlet_h = (
                h_cold_in
                + q_hot / cold["flow_kg_s"]
            )

            solved_temperature = temperature_from_enthalpy(
                cold["fluid_code"],
                target_cold_outlet_h,
                cold["pressure_out"],
                suggested_min_c=cold["temperature_in"] - 100.0,
                suggested_max_c=1200.0,
            )

            if solved_temperature <= cold["temperature_in"]:
                raise ValueError(
                    "The solved cold outlet temperature is not "
                    "above the cold inlet temperature."
                )

            st.session_state["cold_tout_text"] = (
                f"{solved_temperature:.6f}"
            )

            solved_name = "cold-side outlet temperature"
            solved_value = f"{solved_temperature:.6f} °C"

        st.session_state["balance_success"] = (
            f"Calculated {solved_name}: {solved_value}"
        )

    except Exception as error:
        st.session_state["balance_error"] = str(error)


# ============================================================
# PROFILE GENERATION
# ============================================================

def create_temperature_profiles(
    hot,
    cold,
    flow_arrangement,
):
    """
    Generate 10 temperatures for nine equal-duty segments.

    Enthalpy and pressure are interpolated between the actual
    balanced inlet and outlet conditions.
    """
    h_hot_in = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["temperature_in"],
        hot["pressure_in"],
    )

    h_hot_out = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["temperature_out"],
        hot["pressure_out"],
    )

    h_cold_in = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["temperature_in"],
        cold["pressure_in"],
    )

    h_cold_out = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["temperature_out"],
        cold["pressure_out"],
    )

    hot_profile = []
    cold_profile = []

    for index in range(NUMBER_OF_SEGMENTS + 1):
        fraction = index / NUMBER_OF_SEGMENTS

        # Hot side always runs inlet to outlet
        hot_h = (
            h_hot_in
            + fraction * (h_hot_out - h_hot_in)
        )

        hot_pressure = (
            hot["pressure_in"]
            + fraction
            * (
                hot["pressure_out"]
                - hot["pressure_in"]
            )
        )

        if index == 0:
            hot_temperature = hot["temperature_in"]

        elif index == NUMBER_OF_SEGMENTS:
            hot_temperature = hot["temperature_out"]

        else:
            hot_temperature = temperature_from_enthalpy(
                hot["fluid_code"],
                hot_h,
                hot_pressure,
                suggested_min_c=(
                    min(
                        hot["temperature_in"],
                        hot["temperature_out"],
                    )
                    - 50.0
                ),
                suggested_max_c=(
                    max(
                        hot["temperature_in"],
                        hot["temperature_out"],
                    )
                    + 50.0
                ),
            )

        # Cold-side direction depends on arrangement
        if flow_arrangement == "Counter-current":
            cold_h_start = h_cold_out
            cold_h_end = h_cold_in

            cold_pressure_start = cold["pressure_out"]
            cold_pressure_end = cold["pressure_in"]

            cold_temperature_start = (
                cold["temperature_out"]
            )

            cold_temperature_end = (
                cold["temperature_in"]
            )

        else:
            cold_h_start = h_cold_in
            cold_h_end = h_cold_out

            cold_pressure_start = cold["pressure_in"]
            cold_pressure_end = cold["pressure_out"]

            cold_temperature_start = (
                cold["temperature_in"]
            )

            cold_temperature_end = (
                cold["temperature_out"]
            )

        cold_h = (
            cold_h_start
            + fraction * (cold_h_end - cold_h_start)
        )

        cold_pressure = (
            cold_pressure_start
            + fraction
            * (
                cold_pressure_end
                - cold_pressure_start
            )
        )

        if index == 0:
            cold_temperature = cold_temperature_start

        elif index == NUMBER_OF_SEGMENTS:
            cold_temperature = cold_temperature_end

        else:
            cold_temperature = temperature_from_enthalpy(
                cold["fluid_code"],
                cold_h,
                cold_pressure,
                suggested_min_c=(
                    min(
                        cold["temperature_in"],
                        cold["temperature_out"],
                    )
                    - 50.0
                ),
                suggested_max_c=(
                    max(
                        cold["temperature_in"],
                        cold["temperature_out"],
                    )
                    + 50.0
                ),
            )

        hot_profile.append(hot_temperature)
        cold_profile.append(cold_temperature)

    return (
        hot_profile,
        cold_profile,
        h_hot_in,
        h_hot_out,
        h_cold_in,
        h_cold_out,
    )


# ============================================================
# USER INTERFACE
# ============================================================

st.info(
    "Leave exactly one of these fields empty: hot mass flow, "
    "hot outlet temperature, cold mass flow, or cold outlet "
    "temperature. Then click **Balance missing field**."
)

hot_column, cold_column = st.columns(2)

with hot_column:
    side_input_area(
        title="🔴 Hot side",
        side="hot",
        default_fluid="Water",
        default_flow="10000",
        default_tin=90.0,
        default_tout="60",
        default_pressure=5.0,
    )

with cold_column:
    side_input_area(
        title="🔵 Cold side",
        side="cold",
        default_fluid="Water",
        default_flow="10000",
        default_tin=20.0,
        default_tout="",
        default_pressure=5.0,
    )

st.button(
    "⚖️ Balance missing field",
    type="primary",
    on_click=balance_missing_field,
)

if st.session_state.get("balance_success"):
    st.success(st.session_state["balance_success"])

if st.session_state.get("balance_error"):
    st.error(st.session_state["balance_error"])

st.divider()

option_column_1, option_column_2 = st.columns(2)

with option_column_1:
    flow_arrangement = st.radio(
        "Flow arrangement",
        [
            "Counter-current",
            "Co-current",
        ],
        horizontal=True,
    )

with option_column_2:
    geometry_factor = st.number_input(
        "Correction geometry factor",
        min_value=0.01,
        max_value=1.00,
        value=0.90,
        step=0.01,
        format="%.3f",
        help="ETD = WTD × correction geometry factor",
    )


# ============================================================
# MAIN CALCULATION
# ============================================================

try:
    hot = get_stream_data("hot")
    cold = get_stream_data("cold")

    missing_fields = []

    if hot["flow_value"] is None:
        missing_fields.append("hot mass flow")

    if hot["temperature_out"] is None:
        missing_fields.append("hot outlet temperature")

    if cold["flow_value"] is None:
        missing_fields.append("cold mass flow")

    if cold["temperature_out"] is None:
        missing_fields.append("cold outlet temperature")

    if missing_fields:
        st.info(
            "Waiting for heat balance. Missing: "
            + ", ".join(missing_fields)
        )

        st.stop()

    if hot["flow_kg_s"] <= 0:
        raise ValueError(
            "Hot-side mass flow must be positive."
        )

    if cold["flow_kg_s"] <= 0:
        raise ValueError(
            "Cold-side mass flow must be positive."
        )

    (
        hot_profile,
        cold_profile,
        h_hot_in,
        h_hot_out,
        h_cold_in,
        h_cold_out,
    ) = create_temperature_profiles(
        hot,
        cold,
        flow_arrangement,
    )

    q_hot = (
        hot["flow_kg_s"]
        * (h_hot_in - h_hot_out)
    )

    q_cold = (
        cold["flow_kg_s"]
        * (h_cold_out - h_cold_in)
    )

    if q_hot <= 0:
        raise ValueError(
            "Hot-side duty is not positive."
        )

    if q_cold <= 0:
        raise ValueError(
            "Cold-side duty is not positive."
        )

    total_duty = (q_hot + q_cold) / 2.0

    balance_error = (
        abs(q_hot - q_cold)
        / max(abs(q_hot), abs(q_cold))
        * 100.0
    )

    # Standard exchanger LMTD
    if flow_arrangement == "Counter-current":
        terminal_dt_1 = (
            hot["temperature_in"]
            - cold["temperature_out"]
        )

        terminal_dt_2 = (
            hot["temperature_out"]
            - cold["temperature_in"]
        )

    else:
        terminal_dt_1 = (
            hot["temperature_in"]
            - cold["temperature_in"]
        )

        terminal_dt_2 = (
            hot["temperature_out"]
            - cold["temperature_out"]
        )

    overall_lmtd = (
        logarithmic_mean_temperature_difference(
            terminal_dt_1,
            terminal_dt_2,
        )
    )

    # Nine-segment WTD
    wtd, segment_results = calculate_wtd(
        hot_profile,
        cold_profile,
        total_duty,
    )

    # Geometry correction
    etd = wtd * geometry_factor

    if etd <= 0:
        raise ValueError(
            "ETD must be greater than zero."
        )

    required_ua = total_duty / etd

    # ========================================================
    # RESULTS
    # ========================================================

    st.subheader("Results")

    result_1, result_2, result_3, result_4 = (
        st.columns(4)
    )

    result_1.metric(
        "Heat duty",
        f"{total_duty:,.2f} kW",
    )

    result_2.metric(
        "WTD",
        f"{wtd:,.3f} K",
    )

    result_3.metric(
        "ETD",
        f"{etd:,.3f} K",
    )

    result_4.metric(
        "Required UA",
        f"{required_ua:,.3f} kW/K",
    )

    secondary_1, secondary_2, secondary_3 = (
        st.columns(3)
    )

    secondary_1.metric(
        "Standard LMTD",
        f"{overall_lmtd:,.3f} K",
    )

    secondary_2.metric(
        "Geometry factor",
        f"{geometry_factor:.3f}",
    )

    secondary_3.metric(
        "Energy imbalance",
        f"{balance_error:.4f}%",
    )

    if balance_error <= 0.1:
        st.success(
            "Hot and cold heat duties are balanced."
        )
    elif balance_error <= 5.0:
        st.warning(
            "The energy imbalance is below 5%, but the "
            "calculation is not fully balanced."
        )
    else:
        st.error(
            "Energy imbalance exceeds 5%. Leave one balance "
            "field empty and use the automatic solver."
        )

    # ========================================================
    # DUTY DETAILS
    # ========================================================

    with st.expander(
        "Heat-balance details",
        expanded=False,
    ):
        st.write(
            f"Hot-side duty: **{q_hot:,.4f} kW**"
        )

        st.write(
            f"Cold-side duty: **{q_cold:,.4f} kW**"
        )

        st.write(
            f"Hot inlet enthalpy: "
            f"**{h_hot_in:,.4f} kJ/kg**"
        )

        st.write(
            f"Hot outlet enthalpy: "
            f"**{h_hot_out:,.4f} kJ/kg**"
        )

        st.write(
            f"Cold inlet enthalpy: "
            f"**{h_cold_in:,.4f} kJ/kg**"
        )

        st.write(
            f"Cold outlet enthalpy: "
            f"**{h_cold_out:,.4f} kJ/kg**"
        )

    # ========================================================
    # WTD SEGMENT TABLE
    # ========================================================

    with st.expander(
        "Nine-segment WTD calculation",
        expanded=False,
    ):
        st.latex(
            r"WTD="
            r"\frac{Q}"
            r"{\sum_{i=1}^{9}"
            r"\left(\frac{\Delta Q_i}"
            r"{dLMTD_i}\right)}"
        )

        st.dataframe(
            segment_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hot T1 [°C]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "Cold T1 [°C]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "ΔT1 [K]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "Hot T2 [°C]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "Cold T2 [°C]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "ΔT2 [K]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "dLMTD [K]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "dQi [kW]": st.column_config.NumberColumn(
                    format="%.4f"
                ),
                "dQi/dLMTD [kW/K]":
                    st.column_config.NumberColumn(
                        format="%.4f"
                    ),
            },
        )

        sum_dq_over_lmtd = sum(
            row["dQi/dLMTD [kW/K]"]
            for row in segment_results
        )

        st.write(
            "Sum of dQi/dLMTD: "
            f"**{sum_dq_over_lmtd:,.5f} kW/K**"
        )

        st.write(
            f"WTD: **{wtd:,.5f} K**"
        )

        st.write(
            f"ETD = {wtd:,.5f} × "
            f"{geometry_factor:.5f} = "
            f"**{etd:,.5f} K**"
        )

        st.write(
            f"UA = {total_duty:,.5f} / "
            f"{etd:,.5f} = "
            f"**{required_ua:,.5f} kW/K**"
        )

    # ========================================================
    # NATURAL-GAS DETAILS
    # ========================================================

    if (
        hot["fluid_name"] == "Typical natural gas"
        or cold["fluid_name"] == "Typical natural gas"
    ):
        with st.expander(
            "Typical natural-gas composition",
            expanded=False,
        ):
            st.table(
                {
                    "Component": list(
                        NATURAL_GAS_COMPOSITION.keys()
                    ),
                    "Mole fraction [%]": list(
                        NATURAL_GAS_COMPOSITION.values()
                    ),
                }
            )

            st.warning(
                "This is a representative molar composition. "
                "Use the actual gas analysis for project work."
            )

except Exception as error:
    st.error(
        f"Calculation unavailable: {error}"
    )

    st.info(
        "Check the fluid states, absolute pressures, temperature "
        "approaches, and CoolProp validity range."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Calculation basis: Q = ṁΔh · 9 equal-duty segments · "
    "WTD = Q / Σ(dQi/dLMTDi) · ETD = WTD × F · UA = Q/ETD"
)
