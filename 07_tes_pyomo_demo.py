"""
TES Dispatch Optimization Demo

Demonstrates TES module with synthetic data.
For full framework integration, see run.py and ptxclass_r0.py
"""

import pandas as pd
import numpy as np
from pyomo_DTC_CPLEX_TES import roll_cfe

# Example configuration (minimal required parameters)
vars = {
    # Dispatch settings
    'window_size': 48,  # Rolling window size (hours)
    'step_size': 24,    # Step size (hours)
    'dispatch_time': 168,  # Total simulation time (1 week for demo)

    # Load parameters
    'Load_min': 95,   # MW
    'Load_max': 100,  # MW
    'Load_MRR': 5,    # Maximum ramp rate (% per hour)

    # TES parameters (validated June 2026)
    'tes_rte': 0.95,         # Round-trip efficiency (electric heater)
    'tes_CDratio': 3.0,      # Charge/discharge ratio
    'tes_duration': 16,      # Storage duration (hours)
    'tes_st_eff': 37,        # Steam turbine efficiency (%) - avg of 34-39%
    'tes_st_min': 40,        # Minimum load (%) - physics constraint

    # BESS parameters
    'BESS_rte': 0.88,
    'BESS_cyclesperyr': 365,
    'ess_soci': 0.5,  # Initial state of charge

    # LDES parameters (for comparison)
    'LDES_rte': 0.70,
    'LDES_constantloss': 1.0,  # % per day

    # Clean firm
    'cleanfirm_size': 0,  # MW

    # Gas parameters
    'NG_CFE': 0.0,  # Natural gas CFE fraction
    'G1_fc_bfix': 0,
    'G2_fc_bfix': 0,
    'G1_fc_mfix': 0,
    'G2_fc_mfix': 0,
    'G1_fc_bvar': 0,
    'G2_fc_bvar': 0,
    'G1_fc_mvar': 0,
    'G2_fc_mvar': 0,

    # Penalties and incentives
    'NONCFE_pen': 1000,  # Non-CFE penalty ($/MWh)
    'EA_pen': 5,          # BESS arbitrage penalty
    'wind_basis': 0,
    'Lcurtt_pen': 100,
    'wind_ptc_2023': 27.5,
    'fin_esc': 0.02,
    'COD': 2026,

    # Solver settings
    'solve_with_gurobi': 0,  # Use CPLEX by default
    'solve_with_highs': 1,   # Or use HiGHS (open-source)
}

# System sizing
svar = {
    # BESS
    'bessD_kW': 50000,    # 50 MW discharge
    'bessC_kW': 50000,    # 50 MW charge
    'bess_kWh': 200000,   # 200 MWh capacity

    # LDES (generic - for Phase 4 comparisons)
    'ldesD_kW': 0,
    'ldesC_kW': 0,
    'ldes_kWh': 0,

    # TES
    'tesD_kW': 100000,    # 100 MW thermal discharge
    'tes_kWh': 1600000,   # 1,600 MWh thermal capacity (16 hr × 100 MW)

    # Grid
    'maxExpMW': 0,
    'maxImpMW': 0,
}

# Create example time series data (1 week)
hours = 168
time_index = range(hours)

# Simple solar profile (peaks at noon)
solar_profile = np.array([
    0 if (h % 24 < 6 or h % 24 > 18)
    else 150000 * np.sin(np.pi * ((h % 24) - 6) / 12) ** 2
    for h in time_index
])

# Simple wind profile (more consistent, some evening peak)
wind_profile = np.array([
    30000 + 20000 * np.sin(2 * np.pi * (h % 24) / 24 + np.pi/4)
    for h in time_index
])

# Create ops dataframe
dfopsx = pd.DataFrame({
    'Wt': wind_profile,           # Wind generation (kW)
    'St': solar_profile,          # Solar generation (kW)
    'P1': [50] * hours,           # Import price ($/MWh)
    'P2': [45] * hours,           # Export price ($/MWh)
    'CFE': [0.5] * hours,         # Grid CFE fraction
    'PNGt': [40] * hours,         # Natural gas price ($/MMBtu)
    'BXmaxt': [svar['bess_kWh']] * hours,    # BESS max SOC
    'LXmaxt': [svar['ldes_kWh']] * hours,    # LDES max SOC
    'G1_max_kW': [0] * hours,     # Gas turbine 1 max (disabled for demo)
    'G2_max_kW': [0] * hours,     # Gas turbine 2 max (disabled for demo)
    'G1_heatrate_mmbtu_mwh': [7.5] * hours,
    'G2_heatrate_mmbtu_mwh': [8.0] * hours,
}, index=time_index)

print("=" * 60)
print("TES DISPATCH OPTIMIZATION DEMO")
print("=" * 60)
print(f"\nConfiguration:")
print(f"  Datacenter Load: {vars['Load_max']} MW")
print(f"  TES Capacity: {svar['tes_kWh'] / 1000:.0f} MWh thermal ({vars['tes_duration']} hr)")
print(f"  TES Discharge: {svar['tesD_kW'] / 1000:.0f} MW thermal")
print(f"  TES Charge: {svar['tesD_kW'] * vars['tes_CDratio'] / 1000:.0f} MW electric")
print(f"  Steam Turbine: {svar['tesD_kW'] * vars['tes_st_eff'] / 100000:.1f} MW electric (avg {vars['tes_st_eff']}% eff)")
print(f"  Minimum Load: {vars['tes_st_min']}% (physics constraint)")
print(f"\nRunning {vars['dispatch_time']} hour simulation...")
print(f"  Window size: {vars['window_size']} hours")
print(f"  Step size: {vars['step_size']} hours\n")

# Run optimization
try:
    results = roll_cfe(vars=vars, dfopsx=dfopsx, svar=svar, threads=4, P=200)

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    # Calculate key metrics
    total_load = results['Lt'].sum() / 1000  # MWh
    tes_charged = results['TCt'].sum() / 1000  # MWh
    tes_discharged = results['TDt'].sum() / 1000  # MWh thermal
    turbine_output = results['Gtest'].sum() / 1000  # MWh electric
    solar_used = results['St'].sum() / 1000  # MWh
    solar_curtailed = results['Scurtt'].sum() / 1000  # MWh
    wind_used = results['Wt'].sum() / 1000  # MWh

    # Calculate round-trip efficiency
    if tes_charged > 0:
        rte_actual = (turbine_output / tes_charged) * 100
    else:
        rte_actual = 0

    print(f"\nLoad Served: {total_load:.1f} MWh")
    print(f"\nSolar:")
    print(f"  Generated: {solar_used:.1f} MWh")
    print(f"  Curtailed: {solar_curtailed:.1f} MWh ({100*solar_curtailed/solar_used:.1f}%)")
    print(f"\nWind:")
    print(f"  Generated: {wind_used:.1f} MWh")
    print(f"\nTES:")
    print(f"  Charged: {tes_charged:.1f} MWh electric")
    print(f"  Discharged: {tes_discharged:.1f} MWh thermal")
    print(f"  Turbine Output: {turbine_output:.1f} MWh electric")
    print(f"  Round-trip Eff: {rte_actual:.1f}% (expected: 32-33%)")
    print(f"  Avg SOC: {results['TXt'].mean() / 1000:.1f} MWh")
    print(f"  Max SOC: {results['TXt'].max() / 1000:.1f} MWh")

    # Check turbine operation
    turbine_hours = (results['Kstt'] > 0.5).sum()
    print(f"\nTurbine Operation:")
    print(f"  Hours online: {turbine_hours} / {len(results)} ({100*turbine_hours/len(results):.1f}%)")
    print(f"  Avg output (when on): {turbine_output / turbine_hours if turbine_hours > 0 else 0:.1f} MW")

    print(f"\nResults saved to: results.csv")
    results.to_csv('results.csv')

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)

except Exception as e:
    print(f"\nERROR: {e}")
    print("\nMake sure you have:")
    print("  1. Pyomo installed: pip install pyomo")
    print("  2. A solver installed (HiGHS, CPLEX, or Gurobi)")
    print("  3. Required dependencies: pip install -r requirements.txt")
