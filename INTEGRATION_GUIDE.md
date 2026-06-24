# TES Module Integration Guide

Quick reference for integrating TES modules into existing PtXv3 code.

## File Locations

All files are in the repository root directory.

## Key Files

| File | Purpose |
|------|---------|
| `pyomo_DTC_CPLEX_TES.py` | TES dispatch optimization |
| `fin_DTC_TES.py` | TES financial modeling (LCOE) |
| `pyomo_DTC_CPLEX_base.py` | Base dispatch (no TES) |
| `fin_DTC_CPLEX.py` | Base financial (no TES) |

## Integration Options

### Option A: Simple Replacement (Recommended)

Replace imports in the existing code:

**Before (no TES):**
```python
import pyomo_DTC_CPLEX
import fin_DTC_CPLEX

results = pyomo_DTC_CPLEX.roll_cfe(vars, dfopsx, svar)
financials = fin_DTC_CPLEX.build_pfx(vars, svar, results, ...)
```

**After (with TES):**
```python
import pyomo_DTC_CPLEX_TES as pyomo_DTC_CPLEX
import fin_DTC_TES as fin_DTC_CPLEX

results = pyomo_DTC_CPLEX.roll_cfe(vars, dfopsx, svar)  # Same function call!
financials = fin_DTC_CPLEX.build_pfx(vars, svar, results, ...)  # Same function call!
```

### Option B: Conditional Import

Add flexibility to switch between TES and base:

```python
# At top of file
if vars.get('include_tes', 0) == 1:
    import pyomo_DTC_CPLEX_TES as dispatch_module
    import fin_DTC_TES as financial_module
else:
    import pyomo_DTC_CPLEX as dispatch_module
    import fin_DTC_CPLEX as financial_module

# Use same code for both cases
results = dispatch_module.roll_cfe(vars, dfopsx, svar)
financials = financial_module.build_pfx(vars, svar, results, ...)
```

## Required Configuration Parameters

Add these to the `vars` dict or Excel config:

### TES System
```python
vars['include_tes'] = 1              # Enable TES
vars['tes_rte'] = 0.95               # Heater efficiency (95%)
vars['tes_CDratio'] = 3.0            # Charge/discharge ratio (3:1)
vars['tes_duration'] = 16            # Storage duration (hours)
vars['tes_st_eff'] = 37              # Turbine efficiency (%) - avg of 34-39%
vars['tes_st_min'] = 40              # Minimum turbine load (%) - physics limit
```

### TES Costs
```python
vars['capex_TES_storage'] = 40       # $/kWh thermal (Rondo/Anora validated)
vars['capex_TES_turbine'] = 1000     # $/kW electric output
vars['opex_TESfix'] = 3              # $/kWh/yr O&M (low for thermal)
vars['life_TES'] = 30                # System lifetime (years)
vars['fin_TESitc'] = 0.30            # Investment tax credit (30% IRA)
vars['structure_tes'] = 'Integrated' # 'Integrated' or 'Tolled'
```

### TES Sizing
```python
svar['tesD_kW'] = 100000             # Thermal discharge capacity (kW)
svar['tes_kWh'] = 1600000            # Thermal storage capacity (kWh)
```

**Documentation:** `tes_kWh` should equal `tesD_kW × tes_duration` for consistency.

## Sizing Example

For a 100 MW thermal / 16-hour system:

```python
# Thermal side
svar['tesD_kW'] = 100000             # 100 MW thermal discharge
svar['tes_kWh'] = 1600000            # 1,600 MWh = 100 MW × 16 hr

# Electric side (calculated from thermal)
# Charge: 100 MW × 3.0 CDratio = 300 MW electric input
# Discharge: 100 MW × 37% turbine eff = 37 MW electric output
```

## Validation Checklist

Before running optimization:

- [ ] Import statements updated (Option A or B above)
- [ ] All required `vars` parameters added
- [ ] TES sizing parameters in `svar`
- [ ] Sizing internally consistent (kWh = kW × duration)
- [ ] Test demos run successfully:
  ```bash
  python3 07_tes_pyomo_demo.py  # Dispatch test
  python3 08_tes_financial_demo.py  # Financial test
  ```

## Function Signatures (Unchanged)

The TES modules use **identical** function signatures to base modules:

### Dispatch
```python
roll_cfe(vars, dfopsx, svar, threads=None, P=200, pos=0)
```

### Financial
```python
build_pfx(vars, svar, opsx, dftotin, basepath, mode)
```

No code changes needed beyond imports and configuration!

## Troubleshooting

### Import Error
```
ModuleNotFoundError: No module named 'pyomo_DTC_CPLEX_TES'
```
**Fix:** Ensure Python is running from correct directory or add to path:
```python
import sys
sys.path.insert(0, '/path/to/Phase 2 - Clean')
```

### Missing Parameter Error
```
KeyError: 'tes_st_eff'
```
**Fix:** Add all required TES parameters to `vars` dict (see Required Configuration above)

### Solver Error
```
ApplicationError: No solution found
```
**Fix:** Check TES sizing is feasible given load requirements. TES minimum load (40%) may constrain operation.

## Example Integration

Complete example showing before/after:

**Before (base code):**
```python
import pyomo_DTC_CPLEX
import fin_DTC_CPLEX
import pandas as pd

vars = {'window_size': 48, 'step_size': 24, ...}
svar = {'bess_kWh': 200000, 'bessD_kW': 50000, ...}
dfopsx = pd.read_csv('timeseries.csv')

results = pyomo_DTC_CPLEX.roll_cfe(vars, dfopsx, svar)
financials = fin_DTC_CPLEX.build_pfx(vars, svar, results, dfopsx, './', 'opt')
```

**After (with TES):**
```python
import pyomo_DTC_CPLEX_TES as pyomo_DTC_CPLEX  # Changed
import fin_DTC_TES as fin_DTC_CPLEX  # Changed
import pandas as pd

vars = {
    'window_size': 48, 'step_size': 24, ...,
    # Added TES parameters:
    'tes_rte': 0.95, 'tes_duration': 16, 'tes_st_eff': 37,
    'tes_st_min': 40, 'capex_TES_storage': 40,
    'capex_TES_turbine': 1000, 'opex_TESfix': 3,
}
svar = {
    'bess_kWh': 200000, 'bessD_kW': 50000, ...,
    # Added TES sizing:
    'tesD_kW': 100000, 'tes_kWh': 1600000,
}
dfopsx = pd.read_csv('timeseries.csv')

# Same function calls!
results = pyomo_DTC_CPLEX.roll_cfe(vars, dfopsx, svar)
financials = fin_DTC_CPLEX.build_pfx(vars, svar, results, dfopsx, './', 'opt')

# Results now include TES variables:
print(results['TCt'])    # TES charging (kW)
print(results['TDt'])    # TES discharging (kW thermal)
print(results['Gtest'])  # Turbine output (kW electric)
print(results['TXt'])    # TES state of charge (kWh)
```

## Contact

For questions or issues, refer to:
- `README.md` - Full documentation
- `01_TES_Pyomo_Module_Documentation.docx` - Technical details
- `03_How_to_Run_the_Model.docx` - Detailed usage guide
