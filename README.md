# PtXv3 TES Dispatch Optimization

24/7 Carbon-Free Energy dispatch optimization with Thermal Energy Storage (TES) integration.

## Repository Structure

### Core Modules

**Dispatch Optimization:**
- **`pyomo_DTC_CPLEX_TES.py`** - TES-enabled dispatch with validated steam turbine physics
- **`pyomo_DTC_CPLEX_base.py`** - Base dispatch (BESS/LDES only)

**Financial Modeling (LCOE):**
- **`fin_DTC_TES.py`** - TES financial model with CapEx/OpEx/depreciation/ITC
- **`fin_DTC_CPLEX.py`** - Base financial model
- **`fin_GOOG_Q1_26.py`** - Customer-specific financial model

**Framework Integration:**
- **`ptxclass_r0.py`** - Main optimization class
- **`run.py`** - Execution script (Simple/Detailed/Opt modes)

### Quick Start

**Dispatch Demo** (168-hour optimization):
```bash
pip install -r requirements.txt
python3 07_tes_pyomo_demo.py
```

**Financial Demo** (LCOE calculations):
```bash
python3 08_tes_financial_demo.py
```

For full framework integration, configure scenarios in Excel and use `run.py`.

### Supporting Modules
- **`UTILITIES.py`** - Date/time, financial functions, degradation curves
- **`checks.py`** - Configuration validation
- **`sizesystem.py`** - Component capacity calculations
- **`SolarCapexOpex.py`** / **`SolarDC2AC.py`** - Solar utilities

### Documentation
- **`README.md`** - This file (navigation and usage)
- **`01_TES_Pyomo_Module_Documentation.docx`** - Technical documentation
- **`02_Variable_and_Constraint_Reference.docx`** - Variable/constraint reference
- **`03_How_to_Run_the_Model.docx`** - Integration guide
- **`04_Module_Validation_and_Smoke_Tests.docx`** - Testing procedures
- **`05_Module_Architecture_Diagram.svg`** - Architecture diagram

## TES Module Features

### Rolling Window Optimization
Uses 48-hour windows with 24-hour steps for efficiency and realism:
- Captures multi-day weather patterns
- Enables LDES energy banking through tuning inputs
- ~2 seconds per window solve time
- More efficient than full-year MIP approaches

### Validated Parameters

| Parameter | Value | Source |
|-----------|-------|--------|
| Steam turbine efficiency (40% load) | 34% | EPA CHP + NREL SAM |
| Steam turbine efficiency (100% load) | 39% | EPA CHP (36-40% range) |
| Electric heater efficiency | 95% | Industry standard |
| Thermal storage loss | 1%/day | Rondo/Anora vendor data |
| Storage cost | $40/kWh | Rondo/Anora quotes |
| Minimum load constraint | 40% | NREL SAM, MIT research |

### Key Constraints

**TES System:**
- Energy balance: `SOC[t+1] = SOC[t] + charge[t] × η - discharge[t] / η_turbine`
- SOC bounds: `0 ≤ SOC[t] ≤ capacity`
- Charge/discharge limits based on rated power and 3:1 CDratio

**Steam Turbine:**
- 40% minimum load: `discharge ≥ 0.4 × capacity` OR `discharge = 0`
- Efficiency curve: Linear interpolation between 34% (40% load) and 39% (100% load)
- Binary commitment variable for on/off operation

**Power Balance:**
```
Solar + Wind + TES_Output + BESS + LDES + Gas = Datacenter_Load
```

## Integration Instructions

### Option 1: Standalone TES Module

Use TES optimization independently with your own data:

```python
from pyomo_DTC_CPLEX_TES import roll_cfe
import pandas as pd

# Configure system
vars = {
    'window_size': 48,
    'step_size': 24,
    'dispatch_time': 168,
    'tes_rte': 0.95,
    'tes_duration': 16,
    'tes_st_eff': 37,
    'tes_st_min': 40,
    # ... additional parameters
}

# System sizing
svar = {
    'tesD_kW': 100000,     # 100 MW thermal discharge
    'tes_kWh': 1600000,    # 1,600 MWh thermal capacity
    'bessD_kW': 50000,     # BESS sizing
    'bess_kWh': 200000,
}

# Run optimization
results = roll_cfe(vars=vars, dfopsx=timeseries_data, svar=svar)
```

### Option 2: Integrate into Existing PtXv3 Code

**Step 1: Update Imports**

Replace base modules with TES versions when TES is included:

```python
# OLD (without TES):
import pyomo_DTC_CPLEX
import fin_DTC_CPLEX

# NEW (with TES):
import pyomo_DTC_CPLEX_TES as pyomo_DTC_CPLEX
import fin_DTC_TES as fin_DTC_CPLEX
```

Or conditionally import based on configuration:

```python
if vars.get('include_tes', 0) == 1:
    import pyomo_DTC_CPLEX_TES as dispatch_module
    import fin_DTC_TES as financial_module
else:
    import pyomo_DTC_CPLEX as dispatch_module
    import fin_DTC_CPLEX as financial_module

# Use same function calls:
results = dispatch_module.roll_cfe(vars=vars, dfopsx=dfopsx, svar=svar)
financials = financial_module.build_pfx(vars, svar, results, dftotin, basepath, mode)
```

**Step 2: Add TES Configuration Parameters**

Add to your Excel configuration or vars dict:

```python
# TES System Configuration
vars['include_tes'] = 1              # Enable TES
vars['tes_rte'] = 0.95               # Round-trip efficiency
vars['tes_CDratio'] = 3.0            # Charge/discharge ratio
vars['tes_duration'] = 16            # Storage duration (hours)
vars['tes_st_eff'] = 37              # Steam turbine efficiency (%)
vars['tes_st_min'] = 40              # Minimum load (%)

# TES Financial Parameters
vars['capex_TES_storage'] = 40       # $/kWh thermal
vars['capex_TES_turbine'] = 1000     # $/kW electric output
vars['opex_TESfix'] = 3              # $/kWh/yr O&M
vars['life_TES'] = 30                # Years
vars['fin_TESitc'] = 0.30            # Investment tax credit (30%)
vars['structure_tes'] = 'Integrated' # 'Integrated' or 'Tolled'

# TES System Sizing
svar['tesD_kW'] = 100000             # Thermal discharge capacity (kW)
svar['tes_kWh'] = 1600000            # Thermal storage capacity (kWh)
```

**Step 3: Update ptxclass_r0.py (if needed)**

Add conditional import at the top:

```python
# Add near line 25 with other imports
if vars.get('include_tes', 0) == 1:
    import pyomo_DTC_CPLEX_TES as pyomo_DTC_CPLEX
    import fin_DTC_TES as fin_DTC_CPLEX
else:
    import pyomo_DTC_CPLEX
    import fin_DTC_CPLEX
```

**That's it!** The TES modules use identical function signatures, so no other code changes needed.

### Option 3: Full Framework with Excel Config

For complete PtXv3 framework integration:

```python
from ptxclass_r0 import ptx

# Load Excel configuration (with TES parameters added)
df_input = pd.read_excel('Scenarios/config.xlsx', sheet_name='Main')

# Initialize and run
X = ptx(df_input=df_input, basepath='./', scenario='SCENARIO_NAME',
        dtstr='2026-06-23', mode='opt')
results = X.run_optimize(saveflag=1, targetA=0.98, targetB=0.995)
```

### Quick Test

Verify modules work before integration:

```bash
cd "/path/to/Phase 2 - Clean"

# Test dispatch
python3 07_tes_pyomo_demo.py

# Test financials
python3 08_tes_financial_demo.py
```

## Solver Configuration

Supports multiple solvers via Pyomo:
- **HiGHS** (default) - Open-source, no size limits
- **CPLEX** - Commercial, high performance
- **Gurobi** - Commercial, high performance

Set solver in configuration:
```python
vars['solve_with_highs'] = 1  # HiGHS (recommended for most users)
vars['solve_with_gurobi'] = 0  # Gurobi
# Default (neither flag set): CPLEX
```

## Directory Structure

Expected folder structure for full framework:
```
.
├── Data/
│   ├── Wind/          # Wind generation profiles
│   ├── Solar/         # Solar generation profiles
│   ├── Prices/        # Electricity pricing data
│   ├── CFE/           # Grid carbon intensity
│   └── NG/            # Natural gas prices
├── Scenarios/         # Excel configuration files
├── Results/           # Optimization outputs
└── [Python modules]   # This repository
```

For TES demo only, Data/ and Scenarios/ folders are not required.

## Technical Architecture

### Optimization Flow
1. **Configuration Loading** - Parse Excel config or Python dict
2. **Timeseries Assembly** - Load and align wind/solar/price data
3. **Rolling Window Loop** - Iterate through time horizon
4. **Pyomo Model Build** - Construct MIP for each window
5. **Solver Execution** - HiGHS/CPLEX/Gurobi solve
6. **Results Assembly** - Concatenate and post-process

### TES Module Extensions
The TES module extends base dispatch with:
- **TCt** - TES charging (kW electric input)
- **TDt** - TES discharging (kW thermal output)
- **TXt** - TES state of charge (kWh thermal)
- **Gtest** - Steam turbine electric output (kW)
- **Kstt** - Turbine binary commitment {0,1}
- **lTvt** - Thermal losses (kW)

All variables integrate seamlessly into existing power balance constraints.

## Performance

Typical performance metrics:
- **Solve time**: ~2 seconds per 48-hour window
- **Full year**: ~7 iterations × 2 seconds = ~14 seconds
- **Variables per window**: ~1,250 (including TES additions)
- **Memory usage**: <500 MB for year-long optimization

## Requirements

See `requirements.txt` for full dependency list. Key packages:
- `pyomo>=6.6.0` - Optimization modeling
- `highspy>=1.5.0` - HiGHS solver interface
- `pandas>=2.0.0` - Data handling
- `numpy>=1.24.0` - Numerical operations
- `tqdm>=4.65.0` - Progress bars

## License

Confidential and Proprietary © Intersect Power

## Citation

```
24/7 Carbon-Free Energy: Thermal Energy Storage Evaluation
Phase 2: Python Optimization Module
Intersect Power, June 2026
```
