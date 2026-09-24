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
    "Enthalpies and temperature profiles are calculated with CoolProp. "
    "Pressure inputs must be absolute, bar(a)."
)


# ============================================================
# DATABASES
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

FLOW_FACTORS_TO_KG_S = {
    "kg/s": 1.0,
    "kg/h": 1.0 / 3600.0,
    "t/h": 1000.0 / 3600.0,
}

NUMBER_OF_SEGMENTS = 9


# ============================================================
# BASIC CONVERSIONS
# ============================================================

def flow_to_kg_s(value, unit):
    return value * FLOW_FACTORS_TO_KG_S[unit]


def flow_from_kg_s(value, unit):
    return value / FLOW_FACTORS_TO_KG_S[unit]


def temperature_to_k(temperature_c):
    temperature_k = temperature_c + 273.15

    if temperature_k <= 0:
        raise ValueError(
            "Temperature must be above absolute zero."
        )

    return temperature_k


def pressure_to_pa(pressure_bara):
    if pressure_bara <= 0:
        raise ValueError(
            "Absolute pressure must be greater than zero."
        )

    return pressure_bara * 100_000.0


def parse_required(value, field_name):
    text = str(value).strip()

    if text == "":
        raise ValueError(f"{field_name} cannot be empty.")

    return float(text)


# ============================================================
# COOLPROP FUNCTIONS
# ============================================================

@st.cache_data(show_spinner=False)
def enthalpy_kj_kg(fluid, temperature_c, pressure_bara):
    result = PropsSI(
        "Hmass",
        "T",
        temperature_to_k(temperature_c),
        "P",
        pressure_to_pa(pressure_bara),
        fluid,
    )

    if not math.isfinite(result):
        raise ValueError(
            "CoolProp returned an invalid enthalpy."
        )

    return result / 1000.0


@st.cache_data(show_spinner=False)
def temperature_from_enthalpy(
    fluid,
    enthalpy_kj_kg_value,
    pressure_bara,
):
    result = PropsSI(
        "T",
        "Hmass",
        enthalpy_kj_kg_value * 1000.0,
        "P",
        pressure_to_pa(pressure_bara),
        fluid,
    )

    if not math.isfinite(result):
        raise ValueError(
            "CoolProp returned an invalid temperature."
        )

    return result - 273.15


# ============================================================
# TEMPERATURE-DIFFERENCE FUNCTIONS
# ============================================================

def logarithmic_mean_temperature_difference(dt1, dt2):
    if dt1 <= 0 or dt2 <= 0:
        raise ValueError(
            "Zero or negative temperature difference detected."
        )

    if math.isclose(
        dt1,
        dt2,
        rel_tol=1e-10,
        abs_tol=1e-12,
    ):
        return dt1

    return (dt1 - dt2) / math.log(dt1 / dt2)


def calculate_balance_error(q_hot, q_cold):
    denominator = max(abs(q_hot), abs(q_cold))

    if denominator == 0:
        return 0.0

    return abs(q_hot - q_cold) / denominator * 100.0


# ============================================================
# AUTOMATIC HEAT-BALANCE CALLBACK
# ============================================================

def automatically_balance():
    """
    Called when the user clicks Balance and calculate.

    Exactly one of these Streamlit fields must be empty:
    hot_flow_text, hot_tout_text,
    cold_flow_text, cold_tout_text.
    """

    st.session_state.balance_error_message = ""
    st.session_state.balance_success_message = ""

    balance_fields = {
        "hot_flow_text": st.session_state.hot_flow_text,
        "hot_tout_text": st.session_state.hot_tout_text,
        "cold_flow_text": st.session_state.cold_flow_text,
        "cold_tout_text": st.session_state.cold_tout_text,
    }

    empty_fields = [
        key
        for key, value in balance_fields.items()
        if str(value).strip() == ""
    ]

    if len(empty_fields) != 1:
        st.session_state.balance_error_message = (
            "Leave exactly one field empty: hot mass flow, "
            "hot outlet temperature, cold mass flow, "
            "or cold outlet temperature."
        )
        return

    missing = empty_fields[0]

    try:
        hot_fluid = FLUIDS[st.session_state.hot_fluid]
        cold_fluid = FLUIDS[st.session_state.cold_fluid]

        hot_tin = float(st.session_state.hot_tin)
        cold_tin = float(st.session_state.cold_tin)

        hot_pin = float(st.session_state.hot_pin)
        hot_pout = float(st.session_state.hot_pout)
        cold_pin = float(st.session_state.cold_pin)
        cold_pout = float(st.session_state.cold_pout)

        # ----------------------------------------------------
        # Solve missing hot-side flow
        # ----------------------------------------------------

        if missing == "hot_flow_text":
            hot_tout = parse_required(
                st.session_state.hot_tout_text,
                "Hot outlet temperature",
            )

            cold_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.cold_flow_text,
                    "Cold mass flow",
                ),
                st.session_state.cold_flow_unit,
            )

            cold_tout = parse_required(
                st.session_state.cold_tout_text,
                "Cold outlet temperature",
            )

            h_cold_in = enthalpy_kj_kg(
                cold_fluid,
                cold_tin,
                cold_pin,
            )

            h_cold_out = enthalpy_kj_kg(
                cold_fluid,
                cold_tout,
                cold_pout,
            )

            duty = cold_flow * (h_cold_out - h_cold_in)

            h_hot_in = enthalpy_kj_kg(
                hot_fluid,
                hot_tin,
                hot_pin,
            )

            h_hot_out = enthalpy_kj_kg(
                hot_fluid,
                hot_tout,
                hot_pout,
            )

            hot_delta_h = h_hot_in - h_hot_out

            if duty <= 0 or hot_delta_h <= 0:
                raise ValueError(
                    "The entered temperatures do not produce "
                    "a positive heat duty."
                )

            solved_kg_s = duty / hot_delta_h

            solved_display = flow_from_kg_s(
                solved_kg_s,
                st.session_state.hot_flow_unit,
            )

            st.session_state.hot_flow_text = (
                f"{solved_display:.8g}"
            )

            label = "Hot mass flow"
            result = (
                f"{solved_display:.6g} "
                f"{st.session_state.hot_flow_unit}"
            )

        # ----------------------------------------------------
        # Solve missing hot outlet temperature
        # ----------------------------------------------------

        elif missing == "hot_tout_text":
            hot_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.hot_flow_text,
                    "Hot mass flow",
                ),
                st.session_state.hot_flow_unit,
            )

            cold_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.cold_flow_text,
                    "Cold mass flow",
                ),
                st.session_state.cold_flow_unit,
            )

            cold_tout = parse_required(
                st.session_state.cold_tout_text,
                "Cold outlet temperature",
            )

            h_cold_in = enthalpy_kj_kg(
                cold_fluid,
                cold_tin,
                cold_pin,
            )

            h_cold_out = enthalpy_kj_kg(
                cold_fluid,
                cold_tout,
                cold_pout,
            )

            duty = cold_flow * (h_cold_out - h_cold_in)

            if hot_flow <= 0 or duty <= 0:
                raise ValueError(
                    "Mass flow and heat duty must be positive."
                )

            h_hot_in = enthalpy_kj_kg(
                hot_fluid,
                hot_tin,
                hot_pin,
            )

            required_h_hot_out = (
                h_hot_in - duty / hot_flow
            )

            solved_temperature = temperature_from_enthalpy(
                hot_fluid,
                required_h_hot_out,
                hot_pout,
            )

            st.session_state.hot_tout_text = (
                f"{solved_temperature:.8g}"
            )

            label = "Hot outlet temperature"
            result = f"{solved_temperature:.6g} °C"

        # ----------------------------------------------------
        # Solve missing cold-side flow
        # ----------------------------------------------------

        elif missing == "cold_flow_text":
            hot_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.hot_flow_text,
                    "Hot mass flow",
                ),
                st.session_state.hot_flow_unit,
            )

            hot_tout = parse_required(
                st.session_state.hot_tout_text,
                "Hot outlet temperature",
            )

            cold_tout = parse_required(
                st.session_state.cold_tout_text,
                "Cold outlet temperature",
            )

            h_hot_in = enthalpy_kj_kg(
                hot_fluid,
                hot_tin,
                hot_pin,
            )

            h_hot_out = enthalpy_kj_kg(
                hot_fluid,
                hot_tout,
                hot_pout,
            )

            duty = hot_flow * (h_hot_in - h_hot_out)

            h_cold_in = enthalpy_kj_kg(
                cold_fluid,
                cold_tin,
                cold_pin,
            )

            h_cold_out = enthalpy_kj_kg(
                cold_fluid,
                cold_tout,
                cold_pout,
            )

            cold_delta_h = h_cold_out - h_cold_in

            if duty <= 0 or cold_delta_h <= 0:
                raise ValueError(
                    "The entered temperatures do not produce "
                    "a positive heat duty."
                )

            solved_kg_s = duty / cold_delta_h

            solved_display = flow_from_kg_s(
                solved_kg_s,
                st.session_state.cold_flow_unit,
            )

            st.session_state.cold_flow_text = (
                f"{solved_display:.8g}"
            )

            label = "Cold mass flow"
            result = (
                f"{solved_display:.6g} "
                f"{st.session_state.cold_flow_unit}"
            )

        # ----------------------------------------------------
        # Solve missing cold outlet temperature
        # ----------------------------------------------------

        else:
            hot_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.hot_flow_text,
                    "Hot mass flow",
                ),
                st.session_state.hot_flow_unit,
            )

            hot_tout = parse_required(
                st.session_state.hot_tout_text,
                "Hot outlet temperature",
            )

            cold_flow = flow_to_kg_s(
                parse_required(
                    st.session_state.cold_flow_text,
                    "Cold mass flow",
                ),
                st.session_state.cold_flow_unit,
            )

            h_hot_in = enthalpy_kj_kg(
                hot_fluid,
                hot_tin,
                hot_pin,
            )

            h_hot_out = enthalpy_kj_kg(
                hot_fluid,
                hot_tout,
                hot_pout,
            )

            duty = hot_flow * (h_hot_in - h_hot_out)

            if cold_flow <= 0 or duty <= 0:
                raise ValueError(
                    "Mass flow and heat duty must be positive."
                )

            h_cold_in = enthalpy_kj_kg(
                cold_fluid,
                cold_tin,
                cold_pin,
            )

            required_h_cold_out = (
                h_cold_in + duty / cold_flow
            )

            solved_temperature = temperature_from_enthalpy(
                cold_fluid,
                required_h_cold_out,
                cold_pout,
            )

            st.session_state.cold_tout_text = (
                f"{solved_temperature:.8g}"
            )

            label = "Cold outlet temperature"
            result = f"{solved_temperature:.6g} °C"

        st.session_state.balance_success_message = (
            f"{label} calculated automatically: {result}"
        )

    except Exception as error:
        st.session_state.balance_error_message = str(error)


# ============================================================
# PROFILE AND WTD CALCULATION
# ============================================================

def create_temperature_profiles(
    hot,
    cold,
    total_duty,
    flow_arrangement,
):
    """
    Generate 10 profile points for 9 equal-duty segments.

    Counter-current profile direction:
    hot inlet -> hot outlet
    cold outlet -> cold inlet

    Co-current profile direction:
    hot inlet -> hot outlet
    cold inlet -> cold outlet
    """

    hot_temperatures = []
    cold_temperatures = []

    for point in range(NUMBER_OF_SEGMENTS + 1):
        fraction = point / NUMBER_OF_SEGMENTS
        accumulated_duty = total_duty * fraction

        # Hot side always runs from inlet to outlet.
        hot_enthalpy = (
            hot["h_in"]
            - accumulated_duty / hot["flow_kg_s"]
        )

        hot_pressure = (
            hot["pin"]
            + fraction * (hot["pout"] - hot["pin"])
        )

        if flow_arrangement == "Counter-current":
            # Profile is traversed from cold outlet to cold inlet.
            cold_enthalpy = (
                cold["h_out"]
                - accumulated_duty / cold["flow_kg_s"]
            )

            cold_pressure = (
                cold["pout"]
                + fraction * (cold["pin"] - cold["pout"])
            )

        else:
            # Both streams are traversed inlet to outlet.
            cold_enthalpy = (
                cold["h_in"]
                + accumulated_duty / cold["flow_kg_s"]
            )

            cold_pressure = (
                cold["pin"]
                + fraction * (cold["pout"] - cold["pin"])
            )

        hot_temperature = temperature_from_enthalpy(
            hot["fluid_code"],
            hot_enthalpy,
            hot_pressure,
        )

        cold_temperature = temperature_from_enthalpy(
            cold["fluid_code"],
            cold_enthalpy,
            cold_pressure,
        )

        hot_temperatures.append(hot_temperature)
        cold_temperatures.append(cold_temperature)

    return hot_temperatures, cold_temperatures


def calculate_wtd(
    hot_temperatures,
    cold_temperatures,
    total_duty,
    hot_is_hotter,
):
    """
    Excel-equivalent calculation:

    dQi = Q / 9

    dLMTDi = (dT1i - dT2i) / LN(dT1i / dT2i)

    dQ/dLMTDi = dQi / dLMTDi

    WTD = Q / SUM(dQ/dLMTDi)
    """

    duty_per_segment = (
        total_duty / NUMBER_OF_SEGMENTS
    )

    sum_dq_over_lmtd = 0.0
    segment_rows = []

    for index in range(NUMBER_OF_SEGMENTS):
        if hot_is_hotter:
            delta_t_1 = (
                hot_temperatures[index]
                - cold_temperatures[index]
            )

            delta_t_2 = (
                hot_temperatures[index + 1]
                - cold_temperatures[index + 1]
            )

        else:
            # Equivalent to the direction-selection IF in Excel.
            delta_t_1 = (
                cold_temperatures[index]
                - hot_temperatures[index]
            )

            delta_t_2 = (
                cold_temperatures[index + 1]
                - hot_temperatures[index + 1]
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

        sum_dq_over_lmtd += dq_over_lmtd

        segment_rows.append(
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

    if sum_dq_over_lmtd <= 0:
        raise ValueError(
            "The WTD conductance sum is not positive."
        )

    wtd = total_duty / sum_dq_over_lmtd

    return wtd, segment_rows, sum_dq_over_lmtd


# ============================================================
# INPUTS
# ============================================================

hot_column, cold_column = st.columns(2)

with hot_column:
    st.subheader("🔴 Hot side")

    st.selectbox(
        "Fluid",
        options=list(FLUIDS.keys()),
        index=list(FLUIDS.keys()).index("Water"),
        key="hot_fluid",
    )

    flow_1, flow_2 = st.columns(2)

    flow_1.text_input(
        "Mass flow",
        value="10000",
        placeholder="Leave empty to calculate",
        key="hot_flow_text",
    )

    flow_2.selectbox(
        "Flow unit",
        options=list(FLOW_FACTORS_TO_KG_S.keys()),
        index=1,
        key="hot_flow_unit",
    )

    temperature_1, temperature_2 = st.columns(2)

    temperature_1.number_input(
        "Inlet temperature [°C]",
        value=90.0,
        key="hot_tin",
    )

    temperature_2.text_input(
        "Outlet temperature [°C]",
        value="60",
        placeholder="Leave empty to calculate",
        key="hot_tout_text",
    )

    pressure_1, pressure_2 = st.columns(2)

    pressure_1.number_input(
        "Inlet pressure [bar(a)]",
        min_value=0.001,
        value=5.0,
        key="hot_pin",
    )

    pressure_2.number_input(
        "Outlet pressure [bar(a)]",
        min_value=0.001,
        value=5.0,
        key="hot_pout",
    )

with cold_column:
    st.subheader("🔵 Cold side")

    st.selectbox(
        "Fluid",
        options=list(FLUIDS.keys()),
        index=list(FLUIDS.keys()).index("Water"),
        key="cold_fluid",
    )

    flow_1, flow_2 = st.columns(2)

    flow_1.text_input(
        "Mass flow",
        value="",
        placeholder="Leave empty to calculate",
        key="cold_flow_text",
    )

    flow_2.selectbox(
        "Flow unit",
        options=list(FLOW_FACTORS_TO_KG_S.keys()),
        index=1,
        key="cold_flow_unit",
    )

    temperature_1, temperature_2 = st.columns(2)

    temperature_1.number_input(
        "Inlet temperature [°C]",
        value=20.0,
        key="cold_tin",
    )

    temperature_2.text_input(
        "Outlet temperature [°C]",
        value="50",
        placeholder="Leave empty to calculate",
        key="cold_tout_text",
    )

    pressure_1, pressure_2 = st.columns(2)

    pressure_1.number_input(
        "Inlet pressure [bar(a)]",
        min_value=0.001,
        value=5.0,
        key="cold_pin",
    )

    pressure_2.number_input(
        "Outlet pressure [bar(a)]",
        min_value=0.001,
        value=5.0,
        key="cold_pout",
    )

st.divider()

flow_arrangement = st.radio(
    "Flow arrangement",
    options=["Counter-current", "Co-current"],
    horizontal=True,
)

st.info(
    "Leave exactly one mass-flow or outlet-temperature field empty, "
    "then click **Balance and calculate**."
)

st.button(
    "⚖️ Balance and calculate",
    type="primary",
    on_click=automatically_balance,
)

if st.session_state.get("balance_success_message"):
    st.success(
        st.session_state.balance_success_message
    )

if st.session_state.get("balance_error_message"):
    st.error(
        st.session_state.balance_error_message
    )


# ============================================================
# READ THE COMPLETED INPUTS
# ============================================================

balance_input_values = [
    st.session_state.hot_flow_text,
    st.session_state.hot_tout_text,
    st.session_state.cold_flow_text,
    st.session_state.cold_tout_text,
]

if any(
    str(value).strip() == ""
    for value in balance_input_values
):
    st.warning(
        "One field is still empty. Click "
        "**Balance and calculate** to solve it."
    )

    st.stop()


# ============================================================
# FINAL CALCULATION
# ============================================================

try:
    hot_flow = flow_to_kg_s(
        parse_required(
            st.session_state.hot_flow_text,
            "Hot mass flow",
        ),
        st.session_state.hot_flow_unit,
    )

    cold_flow = flow_to_kg_s(
        parse_required(
            st.session_state.cold_flow_text,
            "Cold mass flow",
        ),
        st.session_state.cold_flow_unit,
    )

    hot_tout = parse_required(
        st.session_state.hot_tout_text,
        "Hot outlet temperature",
    )

    cold_tout = parse_required(
        st.session_state.cold_tout_text,
        "Cold outlet temperature",
    )

    if hot_flow <= 0 or cold_flow <= 0:
        raise ValueError(
            "Both mass flows must be greater than zero."
        )

    hot = {
        "fluid_name": st.session_state.hot_fluid,
        "fluid_code": FLUIDS[st.session_state.hot_fluid],
        "flow_kg_s": hot_flow,
        "tin": float(st.session_state.hot_tin),
        "tout": hot_tout,
        "pin": float(st.session_state.hot_pin),
        "pout": float(st.session_state.hot_pout),
    }

    cold = {
        "fluid_name": st.session_state.cold_fluid,
        "fluid_code": FLUIDS[st.session_state.cold_fluid],
        "flow_kg_s": cold_flow,
        "tin": float(st.session_state.cold_tin),
        "tout": cold_tout,
        "pin": float(st.session_state.cold_pin),
        "pout": float(st.session_state.cold_pout),
    }

    hot["h_in"] = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tin"],
        hot["pin"],
    )

    hot["h_out"] = enthalpy_kj_kg(
        hot["fluid_code"],
        hot["tout"],
        hot["pout"],
    )

    cold["h_in"] = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tin"],
        cold["pin"],
    )

    cold["h_out"] = enthalpy_kj_kg(
        cold["fluid_code"],
        cold["tout"],
        cold["pout"],
    )

    q_hot = hot["flow_kg_s"] * (
        hot["h_in"] - hot["h_out"]
    )

    q_cold = cold["flow_kg_s"] * (
        cold["h_out"] - cold["h_in"]
    )

    if q_hot <= 0:
        raise ValueError(
            "The hot-side heat duty is not positive."
        )

    if q_cold <= 0:
        raise ValueError(
            "The cold-side heat duty is not positive."
        )

    balance_error = calculate_balance_error(
        q_hot,
        q_cold,
    )

    total_duty = (q_hot + q_cold) / 2.0

    # --------------------------------------------------------
    # Conventional overall LMTD
    # --------------------------------------------------------

    if flow_arrangement == "Counter-current":
        overall_dt_1 = hot["tin"] - cold["tout"]
        overall_dt_2 = hot["tout"] - cold["tin"]
    else:
        overall_dt_1 = hot["tin"] - cold["tin"]
        overall_dt_2 = hot["tout"] - cold["tout"]

    conventional_lmtd = (
        logarithmic_mean_temperature_difference(
            overall_dt_1,
            overall_dt_2,
        )
    )

    # --------------------------------------------------------
    # Ten temperature points and nine WTD segments
    # --------------------------------------------------------

    hot_temperatures, cold_temperatures = (
        create_temperature_profiles(
            hot,
            cold,
            total_duty,
            flow_arrangement,
        )
    )

    hot_is_hotter = hot["tin"] > cold["tin"]

    wtd, segment_rows, total_ua = calculate_wtd(
        hot_temperatures,
        cold_temperatures,
        total_duty,
        hot_is_hotter,
    )

    # Q / WTD equals SUM(dQi / dLMTDi)
    ua_based_on_wtd = total_duty / wtd

    # ========================================================
    # RESULTS
    # ========================================================

    st.subheader("Results")

    result_1, result_2, result_3, result_4 = st.columns(4)

    result_1.metric(
        "Balanced heat duty",
        f"{total_duty:,.2f} kW",
    )

    result_2.metric(
        "Conventional LMTD",
        f"{conventional_lmtd:,.3f} K",
    )

    result_3.metric(
        "Weighted temperature difference",
        f"{wtd:,.3f} K",
    )

    result_4.metric(
        "UA based on WTD",
        f"{ua_based_on_wtd:,.3f} kW/K",
    )

    duty_1, duty_2, duty_3 = st.columns(3)

    duty_1.metric(
        "Hot-side duty",
        f"{q_hot:,.3f} kW",
    )

    duty_2.metric(
        "Cold-side duty",
        f"{q_cold:,.3f} kW",
    )

    duty_3.metric(
        "Energy imbalance",
        f"{balance_error:,.6f}%",
    )

    if balance_error <= 0.1:
        st.success(
            "The heat balance is within 0.1%."
        )
    else:
        st.warning(
            "The two sides are not fully balanced. "
            "Clear one calculated field and run the balance again."
        )

    # ========================================================
    # DETAILS
    # ========================================================

    with st.expander(
        "Nine-segment WTD calculation",
        expanded=False,
    ):
        st.write(
            f"Number of segments: **{NUMBER_OF_SEGMENTS}**"
        )

        st.write(
            "Duty per segment: "
            f"**{total_duty / NUMBER_OF_SEGMENTS:,.3f} kW**"
        )

        st.write(
            "Sum of dQi/dLMTDi: "
            f"**{total_ua:,.4f} kW/K**"
        )

        st.dataframe(
            segment_rows,
            use_container_width=True,
            hide_index=True,
        )

        st.latex(
            r"""
            WTD =
            \frac{Q}
            {\sum_{i=1}^{9}
            \left(\frac{\Delta Q_i}{dLMTD_i}\right)}
            """
        )

    with st.expander(
        "Enthalpy details",
        expanded=False,
    ):
        details_1, details_2 = st.columns(2)

        with details_1:
            st.markdown("### 🔴 Hot side")
            st.write(
                f"Inlet enthalpy: "
                f"**{hot['h_in']:,.3f} kJ/kg**"
            )
            st.write(
                f"Outlet enthalpy: "
                f"**{hot['h_out']:,.3f} kJ/kg**"
            )
            st.write(
                f"Mass flow: "
                f"**{hot['flow_kg_s']:,.6f} kg/s**"
            )

        with details_2:
            st.markdown("### 🔵 Cold side")
            st.write(
                f"Inlet enthalpy: "
                f"**{cold['h_in']:,.3f} kJ/kg**"
            )
            st.write(
                f"Outlet enthalpy: "
                f"**{cold['h_out']:,.3f} kJ/kg**"
            )
            st.write(
                f"Mass flow: "
                f"**{cold['flow_kg_s']:,.6f} kg/s**"
            )

    if (
        hot["fluid_name"] == "Typical natural gas"
        or cold["fluid_name"] == "Typical natural gas"
    ):
        with st.expander(
            "Typical natural-gas composition"
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
                "This is a representative composition. "
                "Use the actual project gas composition "
                "for project calculations."
            )

except Exception as error:
    st.error(f"Calculation unavailable: {error}")

    st.info(
        "Check the fluid state, absolute pressures, temperatures, "
        "flow rates and possible temperature crossing."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "WTD uses nine equal-duty intervals. "
    "UA shown here is Q/WTD."
)
