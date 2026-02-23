import math
import pandas as pd
import numpy as np
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="CRESTA Cooling UPS TEA Dashboard", layout="wide")
st.title("CRESTA Cooling UPS – Sizing + TEA Dashboard")

# -------------------------
# Helper
# -------------------------
def flow_m3h_per_mw(delta_t_k: float, rho=1000.0, cp=4180.0) -> float:
    return 3600.0 * 1e6 / (rho * cp * delta_t_k)

def money(x: float) -> str:
    if abs(x) >= 1e9: return f"${x/1e9:.2f}B"
    if abs(x) >= 1e6: return f"${x/1e6:.2f}M"
    if abs(x) >= 1e3: return f"${x/1e3:.1f}k"
    return f"${x:.0f}"

def make_bom(modules_qty: int, it_mw: float):
    bom = []
    per_module = [
        ("Plate Heat Exchanger (module)", 1, "ea"),
        ("Pumps (module, N+1)", 2, "ea"),
        ("Motorized Control Valves", 3, "ea"),
        ("Check Valves", 2, "ea"),
        ("Sensors package", 1, "set"),
        ("Controls/PLC + I/O", 1, "set"),
        ("Skid/container + piping", 1, "set"),
        ("Thermal buffer tank + medium", 1, "set"),
    ]
    for name, qty, unit in per_module:
        bom.append((name, qty * modules_qty, unit))

    plant_level = [
        ("Pod supervisory control", max(1, math.ceil(it_mw / 100)), "ea"),
        ("Commissioning test kit + scripts", 1, "set"),
        ("Spare parts kit", max(1, math.ceil(modules_qty * 0.1)), "set"),
    ]
    for row in plant_level:
        bom.append(row)

    return pd.DataFrame(bom, columns=["BOM Item", "Qty", "Unit"])

# -------------------------
# Sidebar inputs
# -------------------------
st.sidebar.header("Inputs")

it_mw = st.sidebar.slider("IT Load (MW)", 1, 1000, 100)
ride_min = st.sidebar.slider("Ride-through (min)", 5, 30, 15)

warm_supply = st.sidebar.number_input("Warm loop supply (°C)", value=32.0, step=0.5)
warm_return = st.sidebar.number_input("Warm loop return (°C)", value=42.0, step=0.5)
delta_t = warm_return - warm_supply
if delta_t <= 0:
    st.sidebar.error("Return temperature must be > supply temperature.")
    st.stop()

warm_fraction = st.sidebar.slider("Warm/economizer share (%)", 40, 90, 60) / 100.0
chilled_fraction = 1.0 - warm_fraction

st.sidebar.markdown("---")
st.sidebar.subheader("Cost assumptions")

capex_chiller_baseline = st.sidebar.number_input("Baseline chiller CAPEX ($/kW)", value=1000, step=50)
capex_chiller_trim = st.sidebar.number_input("Trim chiller CAPEX ($/kW)", value=800, step=50)
capex_economizer = st.sidebar.number_input("Economizer CAPEX ($/kW)", value=250, step=25)

module_mw = st.sidebar.number_input("CRESTA module size (MW)", value=5.0, step=0.5)
module_cost = st.sidebar.number_input("CRESTA module installed cost ($/module)", value=750000, step=50000)

st.sidebar.markdown("---")
st.sidebar.subheader("Energy assumptions")

kwe_per_kw_chiller = st.sidebar.number_input("Chiller kWe/kWcool", value=0.27, step=0.01)
kwe_per_kw_economizer = st.sidebar.number_input("Economizer kWe/kWcool", value=0.035, step=0.005)
load_factor = st.sidebar.slider("Annual load factor", 0.4, 1.0, 0.85, 0.01)
elec_price = st.sidebar.number_input("Electricity price ($/kWh)", value=0.08, step=0.01)

hours = 8760

# -------------------------
# Calculations
# -------------------------
modules_qty = math.ceil(it_mw / module_mw)
buffer_mwh_th = it_mw * (ride_min / 60.0)

flow_per_mw = flow_m3h_per_mw(delta_t)
facility_flow = it_mw * flow_per_mw
module_flow = module_mw * flow_per_mw

baseline_chiller_mw = it_mw
hybrid_trim_chiller_mw = it_mw * chilled_fraction
hybrid_economizer_mw = it_mw * warm_fraction

baseline_capex = baseline_chiller_mw * 1000 * capex_chiller_baseline
hybrid_capex = (
    hybrid_trim_chiller_mw * 1000 * capex_chiller_trim +
    hybrid_economizer_mw * 1000 * capex_economizer +
    modules_qty * module_cost
)
capex_savings = baseline_capex - hybrid_capex
capex_savings_pct = capex_savings / baseline_capex

baseline_kwh = it_mw * 1000 * load_factor * hours * kwe_per_kw_chiller
hybrid_kwh = (
    hybrid_trim_chiller_mw * 1000 * load_factor * hours * kwe_per_kw_chiller +
    hybrid_economizer_mw * 1000 * load_factor * hours * kwe_per_kw_economizer
)
baseline_opex = baseline_kwh * elec_price
hybrid_opex = hybrid_kwh * elec_price
opex_savings = baseline_opex - hybrid_opex
opex_savings_pct = opex_savings / baseline_opex

# -------------------------
# Display
# -------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("IT Load", f"{it_mw} MW")
c2.metric("CRESTA Modules", f"{modules_qty} × {module_mw:.1f} MW")
c3.metric("Thermal buffer", f"{buffer_mwh_th:.2f} MWh_th", f"{ride_min} min")
c4.metric("Warm loop", f"{warm_supply:.1f}/{warm_return:.1f} °C", f"ΔT={delta_t:.1f}K")

st.subheader("Sizing")
left, right = st.columns(2)
with left:
    st.write(f"**Facility flow:** {facility_flow:,.0f} m³/h")
    st.write(f"**Per-module flow:** {module_flow:,.0f} m³/h")
with right:
    st.write(f"**Baseline chillers:** {baseline_chiller_mw:,.1f} MW")
    st.write(f"**Trim chillers:** {hybrid_trim_chiller_mw:,.1f} MW")
    st.write(f"**Economizer capacity:** {hybrid_economizer_mw:,.1f} MW")

st.subheader("CAPEX + OPEX")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Baseline cooling CAPEX", money(baseline_capex))
m2.metric("CRESTA-hybrid CAPEX", money(hybrid_capex))
m3.metric("CAPEX savings", money(capex_savings), f"{capex_savings_pct*100:.1f}%")
m4.metric("Annual OPEX savings", money(opex_savings), f"{opex_savings_pct*100:.1f}%")

summary = pd.DataFrame([
    ["Baseline", baseline_chiller_mw, 0.0, 0, baseline_capex, baseline_opex],
    ["CRESTA-hybrid", hybrid_trim_chiller_mw, hybrid_economizer_mw, modules_qty, hybrid_capex, hybrid_opex],
], columns=["Case", "Chillers (MW)", "Economizer (MW)", "Modules", "CAPEX ($)", "Cooling Elec OPEX ($/yr)"])

st.dataframe(summary, use_container_width=True)

st.subheader("Charts")
sweep = np.array([1,5,10,20,50,100,200,300,500,750,1000], dtype=float)

# Chiller sizing chart
fig1 = plt.figure(figsize=(7,4))
plt.plot(sweep, sweep, marker="o", label="Baseline chillers")
plt.plot(sweep, sweep*chilled_fraction, marker="o", label="Trim chillers")
plt.xlabel("IT Load (MW)")
plt.ylabel("Chiller capacity (MW)")
plt.title("Chiller sizing reduction")
plt.grid(True, alpha=0.3)
plt.legend()
st.pyplot(fig1)

# CAPEX chart
fig2 = plt.figure(figsize=(7,4))
base_caps = sweep*1000*capex_chiller_baseline
hyb_caps = (sweep*chilled_fraction*1000*capex_chiller_trim +
            sweep*warm_fraction*1000*capex_economizer +
            np.ceil(sweep/module_mw)*module_cost)
plt.plot(sweep, base_caps/1e6, marker="o", label="Baseline CAPEX")
plt.plot(sweep, hyb_caps/1e6, marker="o", label="CRESTA-hybrid CAPEX")
plt.plot(sweep, (base_caps-hyb_caps)/1e6, marker="o", label="Savings")
plt.xlabel("IT Load (MW)")
plt.ylabel("CAPEX ($M)")
plt.title("Cooling CAPEX impact")
plt.grid(True, alpha=0.3)
plt.legend()
st.pyplot(fig2)

st.subheader("Scaled BOM")
bom_df = make_bom(modules_qty, it_mw)
st.dataframe(bom_df, use_container_width=True)

st.download_button("Download summary CSV", summary.to_csv(index=False), file_name="cresta_summary.csv")
st.download_button("Download BOM CSV", bom_df.to_csv(index=False), file_name="cresta_bom.csv")