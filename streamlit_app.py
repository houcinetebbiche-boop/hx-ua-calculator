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
    "Fluid enthalpies are calculated with CoolProp at the entered "
    "temperature and absolute pressure."
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


# ============================================================
# CALCULATION FUNCTIONS
# ============================================================

def convert_mass_flow_to_kg_s(value, unit):
    """Convert the selected mass-flow unit to kg/s."""
    return value * FLOW_UNITS[unit]


def temperature_c_to_k(temperature_c):
    """Convert degrees Celsius to kelvin."""
    temperature_k = temperature_c + 273.15

    if temperature_k <= 0:
        raise ValueError(
            "Temperature must be above absolute zero (-273.15 °C)."
        )

    return temperature_k


def pressure_bar_to_pa(pressure_bara):
    """Convert absolute pressure from bar(a) to Pa."""
    if pressure_bara <= 0:
        raise ValueError("Absolute pressure must be greater than zero.")

    return pressure_bara * 100_000.0


@st.cache_data(show_spinner=False)
def get_enthalpy_kj_kg(fluid, temperature_c, pressure_bara):
    """Return specific enthalpy in kJ/kg from CoolProp."""
    temperature_k = temperature_c_to_k(temperature_c)
    pressure_pa = pressure_bar_to_pa(pressure_bara)

    enthalpy_j_kg = PropsSI(
        "H",
        "T",
        temperature_k,
        "P",
        pressure_pa,
        fluid,
    )

    if not math.isfinite(enthalpy_j_kg):
        raise ValueError("CoolProp returned an invalid enthalpy value.")

    return enthalpy_j_kg / 1000.0


@st.cache_data(show_spinner=False)
def get_density_kg_m3(fluid, temperature_c, pressure_bara):
    """Return density in kg/m³ from CoolProp."""
    temperature_k = temperature_c_to_k(temperature_c)
    pressure_pa = pressure_bar_to_pa(pressure_bara)

    density = PropsSI(
        "D",
        "T",
        temperature_k,
        "P",
        pressure_pa,
        fluid,
    )

    if not math.isfinite(density):
        raise ValueError("CoolProp returned an invalid density value.")

    return density


@st.cache_data(show_spinner=False)
def get_cp_kj_kgk(fluid, temperature_c, pressure_bara):
    """Return isobaric heat capacity in kJ/(kg·K)."""
    temperature_k = temperature_c_to_k(temperature_c)
    pressure_pa = pressure_bar_to_pa(pressure_bara)

    cp_j_kgk = PropsSI(
        "Cpmass",
        "T",
        temperature_k,
        "P",
        pressure_pa,
        fluid,
    )

    if not math.isfinite(cp_j_kgk):
        raise ValueError("CoolProp returned an invalid Cp value.")

    return cp_j_kgk / 1000.0


def calculate_lmtd(delta_t_1, delta_t_2):
    """Calculate the logarithmic mean temperature difference."""
    if delta_t_1 <= 0 or delta_t_2 <= 0:
        raise ValueError(
            "A terminal temperature difference is zero or negative. "
            "Check the temperatures and possible temperature crossing."
        )

    if math.isclose(
        delta_t_1,
        delta_t_2,
        rel_tol=1e-9,
        abs_tol=1e-12,
    ):
        return delta_t_1

    return (
        (delta_t_1 - delta_t_2)
        / math.log(delta_t_1 / delta_t_2)
    )


def calculate_balance_error(q_hot, q_cold):
    """Calculate the hot/cold duty imbalance as a percentage."""
    denominator = max(abs(q_hot), abs(q_cold))

    if denominator == 0:
        return 0.0

    return abs(q_hot - q_cold) / denominator * 100.0


# ============================================================
# USER INPUT FUNCTION
# ============================================================

def side_inputs(
    title,
    key,
    default_fluid,
    default_tin,
    default_tout,
    default_pressure,
    default_flow,
):
    st.subheader(title)

    fluid_names = list(FLUIDS.keys())

    fluid_name = st.selectbox(
        "Fluid",
        fluid_names,
        index=fluid_names.index(default_fluid),
        key=f"{key}_fluid",
    )

    flow_column, unit_column = st.columns(2)

    flow_value = flow_column.number_input(
        "Mass flow",
        min_value=0.0,
        value=float(default_flow),
        step=100.0,
        format="%.3f",
        key=f"{key}_flow",
    )

    flow_unit = unit_column.selectbox(
        "Flow unit",
        list(FLOW_UNITS.keys()),
        index=1,
        key=f"{key}_flow_unit",
    )

    inlet_column, outlet_column = st.columns(2)

    temperature_in = inlet_column.number_input(
        "Inlet temperature [°C]",
        value=float(default_tin),
        step=1.0,
        format="%.3f",
        key=f"{key}_tin",
    )

    temperature_out = outlet_column.number_input(
        "Outlet temperature [°C]",
        value=float(default_tout),
        step=1.0,
        format="%.3f",
        key=f"{key}_tout",
    )

    pressure_in_column, pressure_out_column = st.columns(2)

    pressure_in = pressure_in_column.number_input(
        "Inlet pressure [bar(a)]",
        min_value=0.001,
        value=float(default_pressure),
        step=0.1,
        format="%.4f",
        key=f"{key}_pin",
    )

    pressure_out = pressure_out_column.number_input(
        "Outlet pressure [bar(a)]",
        min_value=0.001,
        value=float(default_pressure),
        step=0.1,
        format="%.4f",
        key=f"{key}_pout",
    )

    return {
        "fluid_name": fluid_name,
        "fluid_code": FLUIDS[fluid_name],
        "flow_value": flow_value,
        "flow_unit": flow_unit,
        "flow_kg_s": convert_mass_flow_to_kg_s(
            flow_value,
            flow_unit,
        ),
        "temperature_in": temperature_in,
        "temperature_out": temperature_out,
        "pressure_in": pressure_in,
        "pressure_out": pressure_out,
    }


# ============================================================
# INPUT AREA
# ============================================================

hot_column, cold_column = st.columns(2)

with hot_column:
    hot = side_inputs(
        title="🔴 Hot side",
        key="hot",
        default_fluid="Water",
        default_tin=90.0,
        default_tout=60.0,
        default_pressure=5.0,
        default_flow=10_000.0,
    )

with cold_column:
    cold = side_inputs(
        title="🔵 Cold side",
        key="cold",
        default_fluid="Water",
        default_tin=20.0,
        default_tout=50.0,
        default_pressure=5.0,
        default_flow=10_000.0,
    )

st.divider()

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
    duty_basis = st.selectbox(
        "Duty used for the UA calculation",
        options=[
            "Average of both sides",
            "Hot side",
            "Cold side",
            "Lower duty",
            "Higher duty",
        ],
    )


# ============================================================
# CALCULATION
# ============================================================

try:
    if hot["flow_kg_s"] <= 0:
        raise ValueError(
            "Enter a hot-side mass flow greater than zero."
        )

    if cold["flow_kg_s"] <= 0:
        raise ValueError(
            "Enter a cold-side mass flow greater than zero."
        )

    # Hot-side thermodynamic properties
    h_hot_in = get_enthalpy_kj_kg(
        hot["fluid_code"],
        hot["temperature_in"],
        hot["pressure_in"],
    )

    h_hot_out = get_enthalpy_kj_kg(
        hot["fluid_code"],
        hot["temperature_out"],
        hot["pressure_out"],
    )

    density_hot_in = get_density_kg_m3(
        hot["fluid_code"],
        hot["temperature_in"],
        hot["pressure_in"],
    )

    density_hot_out = get_density_kg_m3(
        hot["fluid_code"],
        hot["temperature_out"],
        hot["pressure_out"],
    )

    cp_hot_in = get_cp_kj_kgk(
        hot["fluid_code"],
        hot["temperature_in"],
        hot["pressure_in"],
    )

    cp_hot_out = get_cp_kj_kgk(
        hot["fluid_code"],
        hot["temperature_out"],
        hot["pressure_out"],
    )

    # Cold-side thermodynamic properties
    h_cold_in = get_enthalpy_kj_kg(
        cold["fluid_code"],
        cold["temperature_in"],
        cold["pressure_in"],
    )

    h_cold_out = get_enthalpy_kj_kg(
        cold["fluid_code"],
        cold["temperature_out"],
        cold["pressure_out"],
    )

    density_cold_in = get_density_kg_m3(
        cold["fluid_code"],
        cold["temperature_in"],
        cold["pressure_in"],
    )

    density_cold_out = get_density_kg_m3(
        cold["fluid_code"],
        cold["temperature_out"],
        cold["pressure_out"],
    )

    cp_cold_in = get_cp_kj_kgk(
        cold["fluid_code"],
        cold["temperature_in"],
        cold["pressure_in"],
    )

    cp_cold_out = get_cp_kj_kgk(
        cold["fluid_code"],
        cold["temperature_out"],
        cold["pressure_out"],
    )

    # Duty in kW:
    # kg/s × kJ/kg = kJ/s = kW
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
            "The calculated hot-side duty is not positive. "
            "Normally, the hot outlet temperature must be lower "
            "than the hot inlet temperature."
        )

    if q_cold <= 0:
        raise ValueError(
            "The calculated cold-side duty is not positive. "
            "Normally, the cold outlet temperature must be higher "
            "than the cold inlet temperature."
        )

    # Terminal temperature differences
    if flow_arrangement == "Counter-current":
        delta_t_1 = (
            hot["temperature_in"]
            - cold["temperature_out"]
        )

        delta_t_2 = (
            hot["temperature_out"]
            - cold["temperature_in"]
        )

    else:
        delta_t_1 = (
            hot["temperature_in"]
            - cold["temperature_in"]
        )

        delta_t_2 = (
            hot["temperature_out"]
            - cold["temperature_out"]
        )

    lmtd = calculate_lmtd(
        delta_t_1,
        delta_t_2,
    )

    if duty_basis == "Hot side":
        design_duty = q_hot

    elif duty_basis == "Cold side":
        design_duty = q_cold

    elif duty_basis == "Lower duty":
        design_duty = min(q_hot, q_cold)

    elif duty_basis == "Higher duty":
        design_duty = max(q_hot, q_cold)

    else:
        design_duty = (q_hot + q_cold) / 2.0

    required_ua = design_duty / lmtd

    balance_error = calculate_balance_error(
        q_hot,
        q_cold,
    )

    # ========================================================
    # MAIN RESULTS
    # ========================================================

    st.subheader("Results")

    result_1, result_2, result_3, result_4 = st.columns(4)

    result_1.metric(
        "Design duty",
        f"{design_duty:,.2f} kW",
    )

    result_2.metric(
        "LMTD",
        f"{lmtd:,.2f} K",
    )

    result_3.metric(
        "Required UA",
        f"{required_ua:,.2f} kW/K",
    )

    result_4.metric(
        "Energy imbalance",
        f"{balance_error:,.2f}%",
    )

    secondary_1, secondary_2 = st.columns(2)

    secondary_1.metric(
        "Hot-side duty",
        f"{q_hot:,.2f} kW",
    )

    secondary_2.metric(
        "Cold-side duty",
        f"{q_cold:,.2f} kW",
    )

    if balance_error <= 5.0:
        st.success(
            "The hot/cold energy balance is within 5%."
        )
    else:
        st.warning(
            "The hot- and cold-side duties differ by more than 5%. "
            "Check the flow rates, temperatures and pressures."
        )

    # ========================================================
    # THERMODYNAMIC DETAILS
    # ========================================================

    with st.expander(
        "Thermodynamic details",
        expanded=False,
    ):
        hot_details, cold_details = st.columns(2)

        with hot_details:
            st.markdown("### 🔴 Hot side")

            st.write(
                f"Fluid: **{hot['fluid_name']}**"
            )

            st.write(
                f"Mass flow: **{hot['flow_kg_s']:,.5f} kg/s**"
            )

            st.write(
                f"Inlet enthalpy: **{h_hot_in:,.3f} kJ/kg**"
            )

            st.write(
                f"Outlet enthalpy: **{h_hot_out:,.3f} kJ/kg**"
            )

            st.write(
                "Enthalpy difference: "
                f"**{h_hot_in - h_hot_out:,.3f} kJ/kg**"
            )

            st.write(
                f"Inlet density: **{density_hot_in:,.3f} kg/m³**"
            )

            st.write(
                f"Outlet density: **{density_hot_out:,.3f} kg/m³**"
            )

            st.write(
                f"Inlet Cp: **{cp_hot_in:,.4f} kJ/(kg·K)**"
            )

            st.write(
                f"Outlet Cp: **{cp_hot_out:,.4f} kJ/(kg·K)**"
            )

            st.write(
                f"Calculated duty: **{q_hot:,.3f} kW**"
            )

        with cold_details:
            st.markdown("### 🔵 Cold side")

            st.write(
                f"Fluid: **{cold['fluid_name']}**"
            )

            st.write(
                f"Mass flow: **{cold['flow_kg_s']:,.5f} kg/s**"
            )

            st.write(
                f"Inlet enthalpy: **{h_cold_in:,.3f} kJ/kg**"
            )

            st.write(
                f"Outlet enthalpy: **{h_cold_out:,.3f} kJ/kg**"
            )

            st.write(
                "Enthalpy difference: "
                f"**{h_cold_out - h_cold_in:,.3f} kJ/kg**"
            )

            st.write(
                f"Inlet density: **{density_cold_in:,.3f} kg/m³**"
            )

            st.write(
                f"Outlet density: **{density_cold_out:,.3f} kg/m³**"
            )

            st.write(
                f"Inlet Cp: **{cp_cold_in:,.4f} kJ/(kg·K)**"
            )

            st.write(
                f"Outlet Cp: **{cp_cold_out:,.4f} kJ/(kg·K)**"
            )

            st.write(
                f"Calculated duty: **{q_cold:,.3f} kW**"
            )

        st.divider()

        st.write(
            f"Flow arrangement: **{flow_arrangement}**"
        )

        st.write(
            f"Terminal temperature difference ΔT₁: "
            f"**{delta_t_1:,.3f} K**"
        )

        st.write(
            f"Terminal temperature difference ΔT₂: "
            f"**{delta_t_2:,.3f} K**"
        )

        st.write(
            f"Logarithmic mean temperature difference: "
            f"**{lmtd:,.3f} K**"
        )

        st.write(
            f"Duty basis: **{duty_basis}**"
        )

    # ========================================================
    # NATURAL-GAS INFORMATION
    # ========================================================

    natural_gas_selected = (
        hot["fluid_name"] == "Typical natural gas"
        or cold["fluid_name"] == "Typical natural gas"
    )

    if natural_gas_selected:
        with st.expander(
            "Typical natural-gas composition",
            expanded=False,
        ):
            st.write(
                "The following fixed composition is used on a "
                "molar basis:"
            )

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
                "This is a representative natural-gas composition. "
                "For project calculations, use the actual gas analysis."
            )

except Exception as error:
    st.error(
        f"Calculation unavailable: {error}"
    )

    st.info(
        "Check that all temperatures and absolute pressures are "
        "inside the selected fluid's valid CoolProp range. "
        "Mixtures can also fail close to saturation or in a "
        "two-phase region."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "Calculation basis: Q = ṁ × Δh and UA = Q / LMTD. "
    "CoolProp pressure inputs are absolute, bar(a)."
)
