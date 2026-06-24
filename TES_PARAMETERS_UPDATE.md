# Phase 2 TES Module - Parameter Updates

## What Changed (June 24, 2026)

### Updated Input Sheet
**File:** `gjt_working_updated.xlsx`

This replaces `gjt_working_input_sheet.xlsx` with corrected parameters based on team feedback.

### Key Updates:

#### 1. **New TES_PARAMS Sheet Added**
Contains all TES-specific parameters:

| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| tes_heater_capex | 200 | $/kW | Resistive heaters |
| tes_heater_opex_fixed | 5 | $/kW-year | Minimal maintenance |
| tes_heater_efficiency | 0.95 | fraction | Standard resistive |
| tes_turbine_capex | 800 | $/kW | Similar to gas turbine |
| tes_turbine_opex_fixed | 15 | $/kW-year | Fixed O&M |
| tes_turbine_opex_var | 3 | $/MWh | **Variable O&M (KEY!)** |
| tes_turbine_size_kW | 100000 | kW | Fixed at load |
| tes_turbine_eff_min | 0.34 | fraction | At 40% load |
| tes_turbine_eff_max | 0.39 | fraction | At 100% load |
| tes_turbine_min_load | 0.40 | fraction | Physics constraint |
| tes_storage_capex | 40 | $/kWh | Thermal mass |
| tes_storage_opex_pct | 0.005 | fraction | 0.5%/year |
| tes_storage_loss_per_day | 0.01 | fraction | 1% heat loss/day |

#### 2. **Gas Pricing File**
**File:** `C4.csv`
- 8760 hours × $4/MMBTU
- Was C0 (zero) before - now corrected

#### 3. **Boiler Parameters (Alternative to NGPP)**
| Parameter | Value | Unit | Notes |
|-----------|-------|------|-------|
| boiler_capex | 300 | $/kW_thermal | Much cheaper than NGPP |
| boiler_efficiency | 0.85 | fraction | NG to thermal |
| boiler_opex_fixed | 10 | $/kW-year | |
| boiler_opex_var | 2 | $/MWh_thermal | |
| boiler_fuel_cfe | 0.0 | fraction | 0 for NG |

## Critical Fix: Marginal Cost Calculation

### Before (WRONG):
```python
# Was comparing CapEx to OpEx - apples to oranges!
tes_cost = amortized_capex / annual_discharge  # ~$121/MWh
gas_cost = fuel_cost_only  # ~$40/MWh

# Decision: Use gas (appears cheaper)
# Result: TES sits idle at 0.8% utilization
```

### After (CORRECT):
```python
# Compare OpEx to OpEx - apples to apples
tes_marginal_cost = turbine_opex_var  # $3/MWh (OpEx only)
gas_marginal_cost = fuel + var_opex   # $48/MWh ($40 fuel + $8 O&M)

# Decision: Use TES whenever available (16× cheaper!)
# Result: TES utilized at 13%+ capacity factor
```

## How to Use Updated Parameters

### In Pyomo Module:

```python
import pandas as pd

# Load TES parameters
tes_params = pd.read_excel('gjt_working_updated.xlsx', sheet_name='TES_PARAMS')
tes_dict = dict(zip(tes_params['Parameter'], tes_params['Value']))

# Use for dispatch decision
def dispatch_logic(t):
    # Compare MARGINAL costs (OpEx only)
    tes_marginal = tes_dict['tes_turbine_opex_var']  # $/MWh
    gas_marginal = gas_fuel_cost + gas_var_opex      # $/MWh

    # Use cheaper option
    if tes_available and tes_marginal < gas_marginal:
        dispatch_tes()
    else:
        dispatch_gas()
```

### For Capital Planning (Separate from Dispatch):

```python
# CapEx calculations (for LCOE, financing, etc.)
tes_total_capex = (
    charge_MW * tes_dict['tes_heater_capex'] * 1000 +
    discharge_MW * tes_dict['tes_turbine_capex'] * 1000 +
    storage_MWh * tes_dict['tes_storage_capex'] * 1000
)

# Apply IRA credit
tes_capex_after_ira = tes_total_capex * 0.70  # 30% credit

# Amortize for LCOE
annual_capital_cost = tes_capex_after_ira * crf

# But DON'T use this for dispatch decisions!
```

## Module Integration Notes

### What Phase 2 Module Should Do:

1. **Read TES parameters** from TES_PARAMS sheet
2. **Use variable OpEx** for dispatch decisions
3. **Track CapEx** separately for financial calculations
4. **Include steam turbine OpEx** in cost model
5. **Use $4/MMBTU gas pricing** from C4.csv

### Dispatch Logic:
```
Decision priority:
1. Use solar/wind if available (free marginal cost)
2. Charge TES if surplus (marginal cost = wear on heaters)
3. Discharge TES if deficit (marginal cost = $3/MWh)
4. Use gas if still deficit (marginal cost = $48/MWh)
```

## Files in Phase 2

### Input Data:
- ✅ `gjt_working_updated.xlsx` - **Use this (new)**
- ❌ `gjt_working_input_sheet.xlsx` - Old version
- ✅ `C4.csv` - Gas pricing at $4/MMBTU

### Code:
- `pyomo_DTC_CPLEX_TES.py` - Main TES module
- Should read from TES_PARAMS sheet
- Should use correct marginal cost logic

### Documentation:
- `TES_PARAMETERS_UPDATE.md` - This file
- `README.md` - Main Phase 2 README
- `INTEGRATION_GUIDE.md` - Integration instructions

## Validation Checklist

When running Phase 2 module, verify:

- [ ] Reading TES parameters from gjt_working_updated.xlsx
- [ ] TES marginal cost = $3/MWh (not $121/MWh)
- [ ] Gas marginal cost = $48/MWh (not $40/MWh)
- [ ] TES utilization > 10% (not 0.8%)
- [ ] Solar CF ~30-33%, Wind CF ~50%
- [ ] Using C4.csv for gas pricing ($4/MMBTU)

## Questions?

If TES utilization is still low (<10%):
1. Check that marginal cost uses OpEx only (not CapEx)
2. Verify gas pricing includes variable O&M
3. Confirm dispatch logic prefers TES over gas when available
4. Check that turbine OpEx variable ($3/MWh) is included

## Summary

**The Fix:** Separate CapEx (for financing) from OpEx (for dispatch)
- **CapEx:** Planning, LCOE, investment decisions
- **OpEx:** Dispatch, hourly decisions, marginal costs

**Result:** TES is 16× cheaper than gas on marginal basis, so it gets used!

**All updates pushed to:** https://github.com/sreyachagarlamudi-stack/phase-2
