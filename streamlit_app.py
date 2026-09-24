import streamlit as st
from CoolProp.CoolProp import PropsSI

st.set_page_config(
    page_title="HX UA Calculator",
    page_icon="🔥",
    layout="centered"
)

st.title("🔥 HX Thermodynamic Property Test")
st.write("Calculate fluid properties using temperature and absolute pressure.")

fluids = {
    "Water": "Water",
    "Carbon dioxide": "CO2",
    "Ammonia": "Ammonia",
    "Propane": "Propane",
    "R134a": "R134a",
}

fluid_name = st.selectbox("Fluid", list(fluids))
temperature_c = st.number_input("Temperature [°C]", value=25.0)
pressure_bara = st.number_input(
    "Absolute pressure [bar(a)]",
    min_value=0.001,
    value=1.01325
)

if st.button("Calculate properties"):
    try:
        fluid = fluids[fluid_name]
        temperature_k = temperature_c + 273.15
        pressure_pa = pressure_bara * 100_000

        enthalpy = PropsSI(
            "H", "T", temperature_k,
            "P", pressure_pa, fluid
        ) / 1000

        density = PropsSI(
            "D", "T", temperature_k,
            "P", pressure_pa, fluid
        )

        cp = PropsSI(
            "C", "T", temperature_k,
            "P", pressure_pa, fluid
        ) / 1000

        st.success("Properties calculated successfully.")

        col1, col2, col3 = st.columns(3)
        col1.metric("Enthalpy", f"{enthalpy:,.2f} kJ/kg")
        col2.metric("Density", f"{density:,.2f} kg/m³")
        col3.metric("Cp", f"{cp:,.4f} kJ/(kg·K)")

    except Exception as error:
        st.error(f"Property calculation failed: {error}")
