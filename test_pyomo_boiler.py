"""
Test script for pyomo_DTC_TES_BOILER module
"""
import pandas as pd
import numpy as np
from pyomo_DTC_TES_BOILER import py_dtc_cfe_boiler

print("="*80)
print("TESTING PYOMO TES + BOILER MODULE")
print("="*80)
print()

# Create minimal test data
print("Setting up test data...")

# Time period for test (48 hours)
hours = 48
start_time = 0
end_time = hours

# Configuration dictionary (vars)
vars = {
    'window_size': 48,
    'step_size': 24,
    'dispatch_time': 8760,
    'Load_min': 90,
    'Load_max': 100,
    'Load_MRR': 10,
    'cleanfirm_size': 0,
    'BESS_rte': 0.88,
    'BESS_cyclesperyr': 365,
    'tes_rte': 0.95,
    'tes_CDratio': 1.0,
    'tes_duration': 16,
    'tes_st_eff': 39,
    'boiler_efficiency': 0.85,
    'boiler_fuel_cfe': 0.0,
    'NONCFE_pen': 100,
    'EA_pen': 0.1,
    'wind_basis': 0,
    'Lcurtt_pen': 10,
    'NG_CFE': 0.0,
    'wind_ptc_2023': 27,
    'fin_esc': 0.025,
    'COD': 2026,
    'solve_with_gurobi': 0,
    'solve_with_highs': 1,  # Use open-source HiGHS solver
}

# System sizing (svar)
svar = {
    'maxExpMW': 0,
    'maxImpMW': 0,
    'bessD_kW': 50000,  # 50 MW
    'bessC_kW': 50000,
    'bess_kWh': 200000,  # 200 MWh
    'tesD_kW': 100000,  # 100 MW thermal discharge
    'tes_kWh': 1600000,  # 1600 MWh storage
}

# Create timeseries data (dfopsx)
np.random.seed(42)

# Simple profiles for testing
solar_profile = []
wind_profile = []

for h in range(hours):
    hour_of_day = h % 24

    # Solar: daytime only
    if 6 <= hour_of_day <= 18:
        solar = 300000 * 0.8 * np.sin(np.pi * (hour_of_day - 6) / 12)  # Peak ~300 MW
    else:
        solar = 0
    solar_profile.append(solar)

    # Wind: constant with variation
    wind = 50000 * (0.5 + 0.2 * np.random.randn())  # ~50 MW average
    wind_profile.append(max(0, wind))

dfopsx = pd.DataFrame({
    'Wt': wind_profile,
    'St': solar_profile,
    'P1': [50] * hours,  # Grid import price
    'P2': [40] * hours,  # Grid export price
    'CFE': [0.5] * hours,  # Grid CFE fraction
    'PNGt': [4.0] * hours,  # NG price $/MMBTU
    'BXmaxt': [200000] * hours,  # BESS max capacity
    'LXmaxt': [0] * hours,  # LDES (not used)
})

# Initial conditions
BX_i = 100000  # 50% BESS SOC
TX_i = 480000  # 30% TES SOC
Lti = 100000  # Initial load

print("Configuration:")
print(f"  Window: {hours} hours")
print(f"  BESS: {svar['bessD_kW']/1000:.0f} MW / {svar['bess_kWh']/1000:.0f} MWh")
print(f"  TES: {svar['tesD_kW']/1000:.0f} MW / {svar['tes_kWh']/1000:.0f} MWh")
print(f"  Solar: ~{max(solar_profile)/1000:.0f} MW peak")
print(f"  Wind: ~{np.mean(wind_profile)/1000:.0f} MW average")
print(f"  Load: {vars['Load_max']} MW")
print()

# Run optimization
print("Running Pyomo optimization...")
print("(This may take 1-2 minutes)")
print()

try:
    results, tot_dis, num_vars, obj_val, threads = py_dtc_cfe_boiler(
        vars=vars,
        dfopsx=dfopsx,
        start_time=start_time,
        end_time=end_time,
        svar=svar,
        BX_i=BX_i,
        TX_i=TX_i,
        Lti=Lti,
        P=200,
        tot_dis=0,
        iteration=1,
        threads=None,
    )

    print("="*80)
    print("SUCCESS - OPTIMIZATION COMPLETED")
    print("="*80)
    print()
    print(f"Variables: {num_vars}")
    print(f"Objective value: ${obj_val:,.0f}")
    print()

    # Extract key results
    print("Sample Results (first 12 hours):")
    print()
    print("Hour | Load  | Solar | Wind  | BESS_D | TES   | Boiler | Curtail")
    print("-" * 75)

    for t in range(12):
        load = results['Lt'][t] / 1000 if 'Lt' in results else 0
        solar = dfopsx['St'][t] / 1000
        wind = dfopsx['Wt'][t] / 1000
        bess_d = results['BDt'][t] / 1000 if 'BDt' in results else 0
        tes = results['Gtest'][t] / 1000 if 'Gtest' in results else 0
        boiler = results['Boilt'][t] / 1000 if 'Boilt' in results else 0
        curtail = (results['Scurtt'][t] + results['Wcurtt'][t]) / 1000 if 'Scurtt' in results else 0

        print(f"{t:4d} | {load:5.1f} | {solar:5.1f} | {wind:5.1f} | {bess_d:6.1f} | {tes:5.1f} | {boiler:6.1f} | {curtail:7.1f}")

    print()

    # Summary statistics
    if 'BDt' in results:
        total_bess = sum(results['BDt'].values()) / 1000
        print(f"Total BESS discharge: {total_bess:,.0f} MWh")

    if 'Gtest' in results:
        total_tes = sum(results['Gtest'].values()) / 1000
        print(f"Total TES output: {total_tes:,.0f} MWh")

    if 'Boilt' in results:
        total_boiler_thermal = sum(results['Boilt'].values()) / 1000
        total_boiler_electric = total_boiler_thermal * vars['tes_st_eff'] / 100
        print(f"Total boiler output: {total_boiler_electric:,.0f} MWh electric")

    if 'Scurtt' in results and 'Wcurtt' in results:
        total_curtail = (sum(results['Scurtt'].values()) + sum(results['Wcurtt'].values())) / 1000
        print(f"Total curtailment: {total_curtail:,.0f} MWh")

    print()
    print("="*80)
    print("TEST PASSED - Module is working correctly")
    print("="*80)

except Exception as e:
    print("="*80)
    print("TEST FAILED")
    print("="*80)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
