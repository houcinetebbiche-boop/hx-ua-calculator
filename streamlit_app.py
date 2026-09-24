import math

import streamlit as st
from CoolProp.CoolProp import PropsSI


# ============================================================
# PAGE
# ============================================================

st.set_page_config(
    page_title="HX UA Calculator",
    page_icon="🔥",
    layout="wide",
)

st.title("🔥 Heat Exchanger UA Calculator")
st.caption(
    "CoolProp properties · Constant pressure per side · "
    "Nine equal-duty WTD segments"
)


# ============================================================
# SETTINGS
# ============================================================

NUMBER_OF_SEGMENTS = 9

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
    "n-Butane": "n-Butane",
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


# ============================================================
# SESSION-STATE DEFAULTS
# ============================================================

DEFAULTS = {
    "hot_fluid": "Water",
    "hot_flow": "10000",
    "hot_flow_unit": "kg/h",
    "hot_tin": 90.0,
    "hot_tout": "60",
    "hot_pressure": 5.0,

    "cold_fluid": "Water",
    "cold_flow": "10000",
    "cold_flow_unit": "kg/h",
    "cold_tin": 20.0,
    "cold_tout": "",
    "cold_pressure": 5.0,

    "balance_success": "",
    "balance_error": "",
}

for state_key, default_value in DEFAULTS.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value


# ============================================================
# CONVERSION FUNCTIONS
# ============================================================

def parse_optional_number(value):
    """
    Convert text to float.

    Empty text returns None.
    Both decimal points and decimal commas are accepted.
    """
    cleaned_value = str(value).strip()

    if cleaned_value == "":
        return None

    return float(cleaned_value.replace(",", "."))


def flow_to_kg_s(value, unit):
    return value * FLOW_UNITS[unit]


def flow_from_kg_s(value, unit):
    return value / FLOW_UNITS[unit]


def temperature_c_to_k(temperature_c):
    temperature_k = temperature_c + 273.15

    if temperature_k <= 0:
        raise ValueError(
            "Temperature must be above -273.15 °C."
        )

    return temperature_k


def pressure_bara_to_pa(pressure_bara):
    """
    Pressure input is absolute bar(a).
    The same pressure is used at all points on one side.
    """
    if pressure_bara <= 0:
        raise ValueError(
            "Absolute pressure must be greater than zero."
        )

    return pressure_bara * 100_000.0


# ============================================================
# COOLPROP FUNCTIONS
# ============================================================

@st.cache_data(show_spinner=False)
def enthalpy_kj_kg(
    fluid_code,
    temperature_c,
    pressure_bara,
):
    """
    Return specific enthalpy in kJ/kg.
    """
    enthalpy_j_kg = PropsSI(
        "Hmass",
        "T",
        temperature_c_to_k(temperature_c),
        "P",
        pressure_bara_to_pa(pressure_bara),
        fluid_code,
    )

    if not math.isfinite(enthalpy_j_kg):
        raise ValueError(
            "CoolProp returned an invalid enthalpy."
        )

    return enthalpy_j_kg / 1000.0


@st.cache_data(show_spinner=False)
def density_kg_m3(
    fluid_code,
    temperature_c,
    pressure_bara,
):
    """
    Return density in kg/m³.
    """
    density = PropsSI(
        "Dmass",
        "T",
        temperature_c_to_k(temperature_c),
        "P",
        pressure_bara_to_pa(pressure_bara),
        fluid_code,
    )

    if not math.isfinite(density):
        raise ValueError(
            "CoolProp returned an invalid density."
        )

    return density


@st.cache_data(show_spinner=False)
def cp_kj_kgk(
    fluid_code,
    temperature_c,
    pressure_bara,
):
    """
    Return Cp in kJ/(kg·K).
    """
    cp_j_kgk = PropsSI(
        "Cpmass",
        "T",
        temperature_c_to_k(temperature_c),
        "P",
        pressure_bara_to_pa(pressure_bara),
        fluid_code,
    )

    if not math.isfinite(cp_j_kgk):
        raise ValueError(
            "CoolProp returned an invalid Cp."
        )

    return cp_j_kgk / 1000.0


def temperature_from_enthalpy(
    fluid_code,
    target_enthalpy_kj_kg,
    pressure_bara,
    lower_temperature_c=-250.0,
    upper_temperature_c=1000.0,
):
    """
    Determine temperature from specific enthalpy and pressure.

    A direct CoolProp flash is attempted first. A numerical
    temperature search is used if the direct flash fails.
    """
    target_enthalpy_j_kg = (
        target_enthalpy_kj_kg * 1000.0
    )

    pressure_pa = pressure_bara_to_pa(
        pressure_bara
    )

    # Direct H-P flash
    try:
        temperature_k = PropsSI(
            "T",
            "Hmass",
            target_enthalpy_j_kg,
            "P",
            pressure_pa,
            fluid_code,
        )

        temperature_c = temperature_k - 273.15

        if math.isfinite(temperature_c):
            return temperature_c

    except Exception:
        pass

    # Numerical fallback
    lower_temperature_c = max(
        lower_temperature_c,
        -272.0,
    )

    valid_points = []
    number_of_scan_points = 500

    for point_number in range(
        number_of_scan_points + 1
    ):
        fraction = (
            point_number / number_of_scan_points
        )

        trial_temperature = (
            lower_temperature_c
            + fraction
            * (
                upper_temperature_c
                - lower_temperature_c
            )
        )

        try:
            trial_enthalpy = enthalpy_kj_kg(
                fluid_code,
                trial_temperature,
                pressure_bara,
            )

            difference = (
                trial_enthalpy
                - target_enthalpy_kj_kg
            )

            if math.isfinite(difference):
                valid_points.append(
                    (
                        trial_temperature,
                        difference,
                    )
                )

        except Exception:
            continue

    for point_number in range(
        len(valid_points) - 1
    ):
        t_low, difference_low = (
            valid_points[point_number]
        )

        t_high, difference_high = (
            valid_points[point_number + 1]
        )

        if abs(difference_low) < 1e-9:
            return t_low

        if difference_low * difference_high <= 0:
            for _ in range(100):
                t_middle = (
                    t_low + t_high
                ) / 2.0

                middle_enthalpy = enthalpy_kj_kg(
                    fluid_code,
                    t_middle,
                    pressure_bara,
                )

                difference_middle = (
                    middle_enthalpy
                    - target_enthalpy_kj_kg
                )

                if abs(difference_middle) < 1e-8:
                    return t_middle

                if (
                    difference_low
                    * difference_middle
                    <= 0
                ):
                    t_high = t_middle
                    difference_high = (
                        difference_middle
                    )
                else:
                    t_low = t_middle
                    difference_low = (
                        difference_middle
                    )

            return (t_low + t_high) / 2.0

    raise ValueError(
        "Could not determine temperature from enthalpy "
        "at the specified pressure."
    )


# ============================================================
# INPUT FUNCTIONS
# ============================================================

def read_stream(side):
    """
    Read one stream from Streamlit session state.
    """
    fluid_name = st.session_state[
        f"{side}_fluid"
    ]

    flow_value = parse_optional_number(
        st.session_state[f"{side}_flow"]
    )

    outlet_temperature = parse_optional_number(
        st.session_state[f"{side}_tout"]
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
            else flow_to_kg_s(
                flow_value,
                flow_unit,
            )
        ),
        "tin": float(
            st.session_state[f"{side}_tin"]
        ),
        "tout": outlet_temperature,

        # Only one constant pressure per side
        "pressure": float(
            st.session_state[
                f"{side}_pressure"
            ]
        ),
    }


def display_stream_inputs(title, side):
    st.subheader(title)

    st.selectbox(
        "Fluid",
        list(FLUIDS.keys()),
        key=f"{side}_fluid",
    )

    flow_column, unit_column = st.columns(2)

    with flow_column:
        st.text_input(
            "Mass flow — may be empty",
            key=f"{side}_flow",
        )

    with unit_column:
        st.selectbox(
            "Flow unit",
            list(FLOW_UNITS.keys()),
            key=f"{side}_flow_unit",
        )

    inlet_column, outlet_column = st.columns(2)

    with inlet_column:
        st.number_input(
            "Inlet temperature [°C]",
            format="%.4f",
            key=f"{side}_tin",
        )

    with outlet_column:
        st.text_input(
            "Outlet temperature [°C] — may be empty",
            key=f"{side}_tout",
        )

    # Exactly one constant pressure field per side
    st.number_input(
        "Constant pressure [bar(a)]",
        min_value=0.001,
        step=0.1,
        format="%.4f",
        key=f"{side}_pressure",
    )


# ============================================================
# HEAT-BALANCE SOLVER
# ============================================================

def balance_missing_field():
    """
    Solve exactly one missing field:

    - Hot mass flow
    - Hot outlet temperature
    - Cold mass flow
    - Cold outlet temperature
    """
    st.session_state["balance_success"] = ""
    st.session_state["balance_error"] = ""

    try:
        hot = read_stream("hot")
        cold = read_stream("cold")

        missing_fields = []

        if hot["flow_value"] is None:
            missing_fields.append("hot_flow")

        if hot["tout"] is None:
            missing_fields.append("hot_tout")

        if cold["flow_value"] is None:
            missing_fields.append("cold_flow")

        if cold["tout"] is None:
            missing_fields.append("cold_tout")

        if len(missing_fields) == 0:
            raise ValueError(
                "No field is empty. Clear exactly one mass-flow "
                "or outlet-temperature field."
            )

        if len(missing_fields) > 1:
            raise ValueError(
                "More than one field is empty. "
                "Leave exactly one field empty."
            )

        missing_field = missing_fields[0]

        h_hot_in = enthalpy_kj_kg(
            hot["fluid_code"],
            hot["tin"],
            hot["pressure"],
        )

        h_cold_in = enthalpy_kj_kg(
            cold["fluid_code"],
            cold["tin"],
            cold["pressure"],
        )

        # ----------------------------------------------------
        # SOLVE HOT MASS FLOW
        # ----------------------------------------------------

        if missing_field == "hot_flow":
            if hot["tout"] is None:
                raise ValueError(
                    "Hot outlet temperature is required."
                )

            if cold["flow_kg_s"] is None:
                raise ValueError(
                    "Cold mass flow is required."
                )

            if cold["tout"] is None:
                raise ValueError(
                    "Cold outlet temperature is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["tout"],
                hot["pressure"],
            )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["tout"],
                cold["pressure"],
            )

            q_cold = (
                cold["flow_kg_s"]
                * (h_cold_out - h_cold_in)
            )

            hot_enthalpy_change = (
                h_hot_in - h_hot_out
            )

            if q_cold <= 0:
                raise ValueError(
                    "Cold-side heat duty must be positive."
                )

            if hot_enthalpy_change <= 0:
                raise ValueError(
                    "Hot-side enthalpy change must be positive."
                )

            solved_flow_kg_s = (
                q_cold / hot_enthalpy_change
            )

            solved_flow_display = flow_from_kg_s(
                solved_flow_kg_s,
                hot["flow_unit"],
            )

            st.session_state["hot_flow"] = (
                f"{solved_flow_display:.8f}"
            )

            st.session_state["balance_success"] = (
                "Hot mass flow calculated: "
                f"{solved_flow_display:.6f} "
                f"{hot['flow_unit']}"
            )

        # ----------------------------------------------------
        # SOLVE COLD MASS FLOW
        # ----------------------------------------------------

        elif missing_field == "cold_flow":
            if hot["flow_kg_s"] is None:
                raise ValueError(
                    "Hot mass flow is required."
                )

            if hot["tout"] is None:
                raise ValueError(
                    "Hot outlet temperature is required."
                )

            if cold["tout"] is None:
                raise ValueError(
                    "Cold outlet temperature is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["tout"],
                hot["pressure"],
            )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["tout"],
                cold["pressure"],
            )

            q_hot = (
                hot["flow_kg_s"]
                * (h_hot_in - h_hot_out)
            )

            cold_enthalpy_change = (
                h_cold_out - h_cold_in
            )

            if q_hot <= 0:
                raise ValueError(
                    "Hot-side heat duty must be positive."
                )

            if cold_enthalpy_change <= 0:
                raise ValueError(
                    "Cold-side enthalpy change must be positive."
                )

            solved_flow_kg_s = (
                q_hot / cold_enthalpy_change
            )

            solved_flow_display = flow_from_kg_s(
                solved_flow_kg_s,
                cold["flow_unit"],
            )

            st.session_state["cold_flow"] = (
                f"{solved_flow_display:.8f}"
            )

            st.session_state["balance_success"] = (
                "Cold mass flow calculated: "
                f"{solved_flow_display:.6f} "
                f"{cold['flow_unit']}"
            )

        # ----------------------------------------------------
        # SOLVE HOT OUTLET TEMPERATURE
        # ----------------------------------------------------

        elif missing_field == "hot_tout":
            if hot["flow_kg_s"] is None:
                raise ValueError(
                    "Hot mass flow is required."
                )

            if cold["flow_kg_s"] is None:
                raise ValueError(
                    "Cold mass flow is required."
                )

            if cold["tout"] is None:
                raise ValueError(
                    "Cold outlet temperature is required."
                )

            h_cold_out = enthalpy_kj_kg(
                cold["fluid_code"],
                cold["tout"],
                cold["pressure"],
            )

            q_cold = (
                cold["flow_kg_s"]
                * (h_cold_out - h_cold_in)
            )

            if q_cold <= 0:
                raise ValueError(
                    "Cold-side heat duty must be positive."
                )

            target_hot_out_enthalpy = (
                h_hot_in
                - q_cold / hot["flow_kg_s"]
            )

            solved_temperature = (
                temperature_from_enthalpy(
                    hot["fluid_code"],
                    target_hot_out_enthalpy,
                    hot["pressure"],
                    lower_temperature_c=-250.0,
                    upper_temperature_c=(
                        hot["tin"] + 500.0
                    ),
                )
            )

            if solved_temperature >= hot["tin"]:
                raise ValueError(
                    "The solved hot outlet temperature "
                    "is not below the hot inlet temperature."
                )

            st.session_state["hot_tout"] = (
                f"{solved_temperature:.8f}"
            )

            st.session_state["balance_success"] = (
                "Hot outlet temperature calculated: "
                f"{solved_temperature:.6f} °C"
            )

        # ----------------------------------------------------
        # SOLVE COLD OUTLET TEMPERATURE
        # ----------------------------------------------------

        elif missing_field == "cold_tout":
            if hot["flow_kg_s"] is None:
                raise ValueError(
                    "Hot mass flow is required."
                )

            if cold["flow_kg_s"] is None:
                raise ValueError(
                    "Cold mass flow is required."
                )

            if hot["tout"] is None:
                raise ValueError(
                    "Hot outlet temperature is required."
                )

            h_hot_out = enthalpy_kj_kg(
                hot["fluid_code"],
                hot["tout"],
                hot["pressure"],
            )

            q_hot = (
                hot["flow_kg_s"]
                * (h_hot_in - h_hot_out)
            )

            if q_hot <= 0:
                raise ValueError(
                    "Hot-side heat duty must be positive."
                )

            target_cold_out_enthalpy = (
                h_cold_in
                + q_hot / cold["flow_kg_s"]
            )

            solved_temperature = (
                temperature_from_enthalpy(
                    cold["fluid_code"],
                    target_cold_out_enthalpy,
                    cold["pressure"],
                    lower_temperature_c=(
                        cold["tin"] - 200.0
                    ),
                    upper_temperature_c=1200.0,
                )
            )

            if solved_temperature <= cold["tin"]:
                raise ValueError(
                    "The solved cold outlet temperature "
                    "is not above the cold inlet temperature."
                )

            st.session_state["cold_tout"] = (
                f"{solved_temperature:.8f}"
            )

            st.session_state["balance_success"] = (
                "Cold outlet temperature calculated: "
                f"{solved_temperature:.6f} °C"
            )

    except Exception as error:
        st.session_state["balance_error"] = str(
            error
        )


# ============================================================
# WTD FUNCTIONS
# ============================================================

def segment_lmtd(delta_t_1, delta_t_2):
    """
    Calculate LMTD for one segment.
    """
    if delta_t_1 <= 0 or delta_t_2 <= 0:
        raise ValueError(
            "Zero or negative temperature difference detected."
        )

    if math.isclose(
        delta_t_1,
        delta_t_2,
        rel_tol=1e-10,
        abs_tol=1e-12,
    ):
        return delta_t_1

    return (
        (delta_t_1 - delta_t_2)
        / math.log(delta_t_1 / delta_t_2)
    )


def create_temperature_profiles(
    hot,
    cold,
    total_duty_kw,
    flow_arrangement,
):
    """
    Create ten temperature boundaries for nine equal-duty
    segments.

    The pressure remains constant on each side.

    Counter-current profile direction:
        Hot:  inlet  -> outlet
        Cold: outlet -> inlet

    Co-current profile direction:
        Hot:  inlet -> outlet
        Cold: inlet -> outlet
    """
    h_hot_in = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tin"],
        hot["pressure"],
    )

    h_hot_out = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tout"],
        hot["pressure"],
    )

    h_cold_in = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tin"],
        cold["pressure"],
    )

    h_cold_out = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tout"],
        cold["pressure"],
    )

    duty_per_segment = (
        total_duty_kw / NUMBER_OF_SEGMENTS
    )

    hot_temperatures = []
    cold_temperatures = []

    for boundary_number in range(
        NUMBER_OF_SEGMENTS + 1
    ):
        accumulated_duty = (
            boundary_number
            * duty_per_segment
        )

        # Hot side: inlet toward outlet
        hot_boundary_enthalpy = (
            h_hot_in
            - accumulated_duty
            / hot["flow_kg_s"]
        )

        if flow_arrangement == "Counter-current":
            # Cold side: outlet toward inlet
            cold_boundary_enthalpy = (
                h_cold_out
                - accumulated_duty
                / cold["flow_kg_s"]
            )

        else:
            # Cold side: inlet toward outlet
            cold_boundary_enthalpy = (
                h_cold_in
                + accumulated_duty
                / cold["flow_kg_s"]
            )

        hot_boundary_temperature = (
            temperature_from_enthalpy(
                hot["fluid_code"],
                hot_boundary_enthalpy,
                hot["pressure"],
                lower_temperature_c=(
                    min(hot["tin"], hot["tout"])
                    - 100.0
                ),
                upper_temperature_c=(
                    max(hot["tin"], hot["tout"])
                    + 100.0
                ),
            )
        )

        cold_boundary_temperature = (
            temperature_from_enthalpy(
                cold["fluid_code"],
                cold_boundary_enthalpy,
                cold["pressure"],
                lower_temperature_c=(
                    min(cold["tin"], cold["tout"])
                    - 100.0
                ),
                upper_temperature_c=(
                    max(cold["tin"], cold["tout"])
                    + 100.0
                ),
            )
        )

        hot_temperatures.append(
            hot_boundary_temperature
        )

        cold_temperatures.append(
            cold_boundary_temperature
        )

    return {
        "hot_temperatures": hot_temperatures,
        "cold_temperatures": cold_temperatures,
        "h_hot_in": h_hot_in,
        "h_hot_out": h_hot_out,
        "h_cold_in": h_cold_in,
        "h_cold_out": h_cold_out,
    }


def calculate_wtd(
    hot_temperatures,
    cold_temperatures,
    total_duty_kw,
):
    """
    Excel calculation:

        dQi = Q / 9

        dLMTDi =
            (ΔT1i - ΔT2i)
            / LN(ΔT1i / ΔT2i)

        dQi/dLMTDi = dQi / dLMTDi

        WTD =
            Q / SUM(dQi/dLMTDi)
    """
    duty_per_segment = (
        total_duty_kw / NUMBER_OF_SEGMENTS
    )

    sum_dq_over_lmtd = 0.0
    segment_results = []

    for segment_index in range(
        NUMBER_OF_SEGMENTS
    ):
        hot_t_1 = hot_temperatures[
            segment_index
        ]

        hot_t_2 = hot_temperatures[
            segment_index + 1
        ]

        cold_t_1 = cold_temperatures[
            segment_index
        ]

        cold_t_2 = cold_temperatures[
            segment_index + 1
        ]

        # Equivalent to the workbook's subtraction-direction logic
        delta_t_1 = abs(hot_t_1 - cold_t_1)
        delta_t_2 = abs(hot_t_2 - cold_t_2)

        incremental_lmtd = segment_lmtd(
            delta_t_1,
            delta_t_2,
        )

        dq_over_lmtd = (
            duty_per_segment
            / incremental_lmtd
        )

        sum_dq_over_lmtd += dq_over_lmtd

        segment_results.append(
            {
                "Segment": segment_index + 1,
                "Hot T1 [°C]": hot_t_1,
                "Cold T1 [°C]": cold_t_1,
                "ΔT1 [K]": delta_t_1,
                "Hot T2 [°C]": hot_t_2,
                "Cold T2 [°C]": cold_t_2,
                "ΔT2 [K]": delta_t_2,
                "dLMTD [K]": incremental_lmtd,
                "dQi [kW]": duty_per_segment,
                "dQi/dLMTD [kW/K]": (
                    dq_over_lmtd
                ),
            }
        )

    if sum_dq_over_lmtd <= 0:
        raise ValueError(
            "The WTD conductance sum is not positive."
        )

    wtd = (
        total_duty_kw
        / sum_dq_over_lmtd
    )

    return (
        wtd,
        sum_dq_over_lmtd,
        segment_results,
    )


# ============================================================
# INPUT AREA
# ============================================================

st.info(
    "Leave exactly one mass-flow or outlet-temperature field "
    "empty, then click **Balance missing field**."
)

hot_column, cold_column = st.columns(2)

with hot_column:
    display_stream_inputs(
        "🔴 Hot side",
        "hot",
    )

with cold_column:
    display_stream_inputs(
        "🔵 Cold side",
        "cold",
    )

st.button(
    "⚖️ Balance missing field",
    type="primary",
    on_click=balance_missing_field,
)

if st.session_state["balance_success"]:
    st.success(
        st.session_state["balance_success"]
    )

if st.session_state["balance_error"]:
    st.error(
        st.session_state["balance_error"]
    )

st.divider()


# ============================================================
# CALCULATION OPTIONS
# ============================================================

option_column_1, option_column_2 = st.columns(2)

with option_column_1:
    flow_arrangement = st.radio(
        "Flow arrangement",
        options=[
            "Counter-current",
            "Co-current",
        ],
        horizontal=True,
    )

with option_column_2:
    geometry_factor = st.number_input(
        "Geometry factor",
        min_value=0.001,
        max_value=1.000,
        value=0.900,
        step=0.010,
        format="%.3f",
    )


# ============================================================
# MAIN CALCULATION
# ============================================================

try:
    hot = read_stream("hot")
    cold = read_stream("cold")

    missing_fields = []

    if hot["flow_value"] is None:
        missing_fields.append(
            "hot mass flow"
        )

    if hot["tout"] is None:
        missing_fields.append(
            "hot outlet temperature"
        )

    if cold["flow_value"] is None:
        missing_fields.append(
            "cold mass flow"
        )

    if cold["tout"] is None:
        missing_fields.append(
            "cold outlet temperature"
        )

    if missing_fields:
        st.info(
            "Waiting for heat balance. Missing: "
            + ", ".join(missing_fields)
        )

        st.stop()

    if hot["flow_kg_s"] <= 0:
        raise ValueError(
            "Hot mass flow must be greater than zero."
        )

    if cold["flow_kg_s"] <= 0:
        raise ValueError(
            "Cold mass flow must be greater than zero."
        )

    if hot["tin"] <= hot["tout"]:
        raise ValueError(
            "Hot inlet temperature must be above "
            "hot outlet temperature."
        )

    if cold["tout"] <= cold["tin"]:
        raise ValueError(
            "Cold outlet temperature must be above "
            "cold inlet temperature."
        )

    # --------------------------------------------------------
    # ENDPOINT ENTHALPIES
    # Same constant pressure at inlet and outlet
    # --------------------------------------------------------

    h_hot_in = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tin"],
        hot["pressure"],
    )

    h_hot_out = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tout"],
        hot["pressure"],
    )

    h_cold_in = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tin"],
        cold["pressure"],
    )

    h_cold_out = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tout"],
        cold["pressure"],
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

    balance_error = (
        abs(q_hot - q_cold)
        / max(abs(q_hot), abs(q_cold))
        * 100.0
    )

    if balance_error > 0.1:
        raise ValueError(
            f"Energy imbalance is {balance_error:.3f}%. "
            "Clear one mass-flow or outlet-temperature field "
            "and click Balance missing field."
        )

    # The balance solver makes these equal.
    # The hot-side duty is used as the single calculation duty.
    total_duty = q_hot

    # --------------------------------------------------------
    # EQUAL-DUTY TEMPERATURE PROFILES
    # --------------------------------------------------------

    profile_data = create_temperature_profiles(
        hot,
        cold,
        total_duty,
        flow_arrangement,
    )

    # --------------------------------------------------------
    # WTD
    # --------------------------------------------------------

    (
        wtd,
        sum_dq_over_lmtd,
        segment_results,
    ) = calculate_wtd(
        profile_data["hot_temperatures"],
        profile_data["cold_temperatures"],
        total_duty,
    )

    if geometry_factor <= 0:
        raise ValueError(
            "Geometry factor must be greater than zero."
        )

    required_ua = (
        total_duty
        / (wtd * geometry_factor)
    )

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
        "Geometry factor",
        f"{geometry_factor:.3f}",
    )

    result_4.metric(
        "Required UA",
        f"{required_ua:,.3f} kW/K",
    )

    st.success(
        "Heat balance completed successfully."
    )

    # ========================================================
    # HEAT-BALANCE DETAILS
    # ========================================================

    with st.expander(
        "Heat-balance details",
        expanded=False,
    ):
        detail_1, detail_2 = st.columns(2)

        with detail_1:
            st.markdown("### 🔴 Hot side")

            st.write(
                f"Fluid: **{hot['fluid_name']}**"
            )

            st.write(
                f"Mass flow: "
                f"**{hot['flow_kg_s']:,.6f} kg/s**"
            )

            st.write(
                f"Constant pressure: "
                f"**{hot['pressure']:,.4f} bar(a)**"
            )

            st.write(
                f"Inlet enthalpy: "
                f"**{h_hot_in:,.4f} kJ/kg**"
            )

            st.write(
                f"Outlet enthalpy: "
                f"**{h_hot_out:,.4f} kJ/kg**"
            )

            st.write(
                f"Duty: **{q_hot:,.4f} kW**"
            )

        with detail_2:
            st.markdown("### 🔵 Cold side")

            st.write(
                f"Fluid: **{cold['fluid_name']}**"
            )

            st.write(
                f"Mass flow: "
                f"**{cold['flow_kg_s']:,.6f} kg/s**"
            )

            st.write(
                f"Constant pressure: "
                f"**{cold['pressure']:,.4f} bar(a)**"
            )

            st.write(
                f"Inlet enthalpy: "
                f"**{h_cold_in:,.4f} kJ/kg**"
            )

            st.write(
                f"Outlet enthalpy: "
                f"**{h_cold_out:,.4f} kJ/kg**"
            )

            st.write(
                f"Duty: **{q_cold:,.4f} kW**"
            )

        st.write(
            f"Energy imbalance: "
            f"**{balance_error:.6f}%**"
        )

    # ========================================================
    # WTD DETAILS
    # ========================================================

    with st.expander(
        "Nine-segment WTD calculation",
        expanded=False,
    ):
        st.write(
            f"Number of segments: "
            f"**{NUMBER_OF_SEGMENTS}**"
        )

        st.write(
            f"Duty per segment: "
            f"**{total_duty / NUMBER_OF_SEGMENTS:,.5f} kW**"
        )

        st.dataframe(
            segment_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Hot T1 [°C]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "Cold T1 [°C]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "ΔT1 [K]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "Hot T2 [°C]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "Cold T2 [°C]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "ΔT2 [K]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "dLMTD [K]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "dQi [kW]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
                "dQi/dLMTD [kW/K]":
                    st.column_config.NumberColumn(
                        format="%.5f"
                    ),
            },
        )

        st.write(
            "Sum of dQi/dLMTD: "
            f"**{sum_dq_over_lmtd:,.6f} kW/K**"
        )

        st.write(
            f"WTD: **{wtd:,.6f} K**"
        )

    # ========================================================
    # FLUID PROPERTY DETAILS
    # ========================================================

    with st.expander(
        "Endpoint fluid properties",
        expanded=False,
    ):
        property_1, property_2 = st.columns(2)

        with property_1:
            st.markdown("### 🔴 Hot side")

            st.write(
                "Inlet density: "
                f"**{density_kg_m3(hot['fluid_code'], hot['tin'], hot['pressure']):,.4f} kg/m³**"
            )

            st.write(
                "Outlet density: "
                f"**{density_kg_m3(hot['fluid_code'], hot['tout'], hot['pressure']):,.4f} kg/m³**"
            )

            st.write(
                "Inlet Cp: "
                f"**{cp_kj_kgk(hot['fluid_code'], hot['tin'], hot['pressure']):,.5f} kJ/(kg·K)**"
            )

            st.write(
                "Outlet Cp: "
                f"**{cp_kj_kgk(hot['fluid_code'], hot['tout'], hot['pressure']):,.5f} kJ/(kg·K)**"
            )

        with property_2:
            st.markdown("### 🔵 Cold side")

            st.write(
                "Inlet density: "
                f"**{density_kg_m3(cold['fluid_code'], cold['tin'], cold['pressure']):,.4f} kg/m³**"
            )

            st.write(
                "Outlet density: "
                f"**{density_kg_m3(cold['fluid_code'], cold['tout'], cold['pressure']):,.4f} kg/m³**"
            )

            st.write(
                "Inlet Cp: "
                f"**{cp_kj_kgk(cold['fluid_code'], cold['tin'], cold['pressure']):,.5f} kJ/(kg·K)**"
            )

            st.write(
                "Outlet Cp: "
                f"**{cp_kj_kgk(cold['fluid_code'], cold['tout'], cold['pressure']):,.5f} kJ/(kg·K)**"
            )

    # ========================================================
    # NATURAL-GAS COMPOSITION
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


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Calculation basis: Q = ṁΔh · Nine equal-duty segments · "
    "Constant pressure on each side"
)
