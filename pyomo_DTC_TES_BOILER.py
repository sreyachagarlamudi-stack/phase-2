import pyomo.environ as pyo
import pandas as pd
import numpy as np
import os
from tqdm import tqdm

"""
TES + Boiler + Steam Header Dispatch Optimization Module
Extends pyomo_DTC_CPLEX_TES with boiler + steam header architecture

Key Features:
- BESS for short-duration storage
- TES for long-duration thermal storage
- Boiler + steam header architecture (replaces direct NGPP)
- Multi-block turbine configuration (4×25 MW)
- Steam header receives heat from TES or boiler
- De-linked power and capacity costs
"""

def roll_cfe(vars, dfopsx, svar, threads=None, P=200, pos=0):
    """
    Rolling window optimization for TES + Boiler dispatch.
    """
    pymodel = py_dtc_cfe_boiler

    final_results = pd.DataFrame()
    final_results.index.name = 'Hour'
    int_value = []
    i = 0

    window_size = int(vars['window_size'])
    step_size = int(vars['step_size'])
    num_hours = int(vars['dispatch_time'])

    iteration = 0

    if threads:
        pbar = tqdm(range(0, num_hours - step_size + 1, step_size),
                   desc=f"Core {pos}",
                   position=pos,
                   leave=False)
    else:
        pbar = tqdm(range(0, num_hours - step_size + 1, step_size), desc="Running Model")

    for start in pbar:
        if start == 0:
            end = start + window_size

            BX_init = svar['bess_kWh'] * vars['ess_soci']
            TX_init = svar['tes_kWh'] * vars['ess_soci']
            Lt_init = vars['Load_max'] * 1000

            tot_dis = 0
            iteration += 1

            results, tot_dis, num_vars, obj_val, threads = pymodel(
                vars=vars,
                dfopsx=dfopsx,
                start_time=start,
                end_time=end,
                svar=svar,
                BX_i=BX_init,
                TX_i=TX_init,
                Lti=Lt_init,
                P=P,
                tot_dis=tot_dis,
                iteration=iteration,
                threads=threads,
            )
            pbar.set_postfix(vars=num_vars, obj=f"{obj_val:,.0f}", threads=threads)

            df_window = pd.DataFrame(results, index=range(start, end))
            df_results_step = df_window.iloc[:step_size]
            int_value.append(df_results_step)

            i += 1

        else:
            end = min(start + window_size, num_hours)

            BX_init = int_value[i]['BXt'][start - 1]
            TX_init = int_value[i]['TXt'][start - 1]
            Lt_init = int_value[i]['Lt'][start - 1]

            iteration += 1

            results, tot_dis, num_vars, obj_val, threads = pymodel(
                vars=vars,
                dfopsx=dfopsx,
                start_time=start,
                end_time=end,
                svar=svar,
                BX_i=BX_init,
                TX_i=TX_init,
                Lti=Lt_init,
                P=P,
                tot_dis=tot_dis,
                iteration=iteration,
                threads=threads,
            )
            pbar.set_postfix(vars=num_vars, obj=f"{obj_val:,.0f}", threads=threads)

            df_window = pd.DataFrame(results, index=range(start, end))
            int_value.append(df_window)

            break

    final_results = pd.concat(int_value)

    for col in ['Wt', 'St', 'P1', 'P2', 'CFE', 'PNGt']:
        if col in dfopsx.columns:
            final_results[col] = dfopsx[col].iloc[:len(final_results)].values

    return final_results


def py_dtc_cfe_boiler(vars, dfopsx, start_time, end_time, svar, BX_i, TX_i, Lti, P, tot_dis, iteration, threads=None):
    """
    Pyomo model with boiler + steam header architecture.

    Key changes from base TES model:
    - Removed LDES (replaced with TES)
    - Added boiler thermal generation
    - Steam header receives heat from TES or boiler
    - Uses NG variables for boiler fuel
    """
    time = [i for i in range(start_time, end_time)]

    model = pyo.ConcreteModel()
    model.T = pyo.Set(initialize=time)

    ## PARAMETERS ##
    # Timeseries
    model.P1t = pyo.Param(model.T, initialize={t: dfopsx['P1'][t] for t in time})
    model.P2t = pyo.Param(model.T, initialize={t: dfopsx['P2'][t] for t in time})
    model.Wt = pyo.Param(model.T, initialize={t: dfopsx['Wt'][t] for t in time})
    model.St = pyo.Param(model.T, initialize={t: dfopsx['St'][t] for t in time})
    model.Gcfet = pyo.Param(model.T, initialize={t: dfopsx['CFE'][t] for t in time})
    model.PNGt = pyo.Param(model.T, initialize={t: dfopsx['PNGt'][t] for t in time})
    model.BXmaxt = pyo.Param(model.T, initialize={t: dfopsx['BXmaxt'][t] for t in time})
    model.CleanFirm = pyo.Param(model.T, initialize={t: (vars['cleanfirm_size'] * 1000) for t in time})

    # Load
    model.Lmin = pyo.Param(initialize=vars['Load_min'] * 1000.0)
    model.Lmax = pyo.Param(initialize=vars['Load_max'] * 1000.0)
    model.dLmax = pyo.Param(initialize=vars['Load_max'] * 1000.0 * vars['Load_MRR'] / 100.0)

    # Power flow
    model.exmax = pyo.Param(initialize=1000 * svar['maxExpMW'])
    model.impmax = pyo.Param(initialize=1000 * svar['maxImpMW'])

    # BESS
    model.BessDlim = pyo.Param(initialize=svar['bessD_kW'])
    model.BessClim = pyo.Param(initialize=svar['bessC_kW'])
    model.Brte = pyo.Param(initialize=vars['BESS_rte'])

    # TES parameters
    model.TDmax = pyo.Param(initialize=svar['tesD_kW'])
    model.TCmax = pyo.Param(initialize=svar['tesD_kW'] * vars['tes_CDratio'])
    model.TXmax = pyo.Param(initialize=svar['tesD_kW'] * vars['tes_duration'])
    model.Teff = pyo.Param(initialize=vars['tes_rte'])

    # Steam turbine (multi-block configuration)
    model.T3max = pyo.Param(initialize=svar['tesD_kW'] * vars['tes_st_eff'] / 100.0)
    model.GTeff = pyo.Param(initialize=vars['tes_st_eff'] / 100.0)

    # Boiler parameters
    model.BoilerTmax = pyo.Param(initialize=svar['tesD_kW'])  # Max thermal output
    model.BoilerEff = pyo.Param(initialize=vars.get('boiler_efficiency', 0.85))
    model.BoilerFuelCFE = pyo.Param(initialize=vars.get('boiler_fuel_cfe', 0.0))  # 0 for NG

    # Initial conditions
    model.BXi = pyo.Param(initialize=BX_i)
    model.TXi = pyo.Param(initialize=TX_i)
    model.Lti = pyo.Param(initialize=Lti)

    # Penalties
    model.PenNonCFE = pyo.Param(initialize=vars['NONCFE_pen'])
    model.PenBCA = pyo.Param(initialize=vars['EA_pen'])
    model.PenWindBasis = pyo.Param(initialize=vars['wind_basis'])
    model.PenLcurtt = pyo.Param(initialize=vars['Lcurtt_pen'])

    # Fuel
    model.NGcfe = pyo.Param(initialize=vars['NG_CFE'])
    model.Wptc = pyo.Param(initialize=vars['wind_ptc_2023'] * ((1 + vars['fin_esc']) ** (vars['COD'] - 2023)))
    model.Pload = pyo.Param(initialize=P)

    model.bigM = pyo.Param(initialize=1e12)
    model.cycle_d_ratio = pyo.Param(initialize=vars['BESS_cyclesperyr'] / 365.0)

    ## VARIABLES ##
    # Power flows
    model.Lt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Lcurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.dLt = pyo.Var(model.T, within=pyo.Reals, initialize=0.0)
    model.Scurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Wcurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Zt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Xt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)

    # BESS
    model.BCt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.BDt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.BXt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.lBt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)

    # TES
    model.TCt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.TDt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.TXt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.lTvt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)

    # Boiler
    model.Boilt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)  # Thermal output (kW)
    model.Gboilt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)  # Fuel consumption (MMBTU/hr)

    # Steam header and turbine
    model.SThermt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)  # Steam header thermal (kW)
    model.Gtest = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)  # Turbine output (kW electric)

    # BESS state
    model.KBct = pyo.Var(model.T, within=pyo.Binary)

    # Carbon fraction
    model.Ct = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)

    ## OBJECTIVE ##
    def obj(m):
        return (sum(
            m.Lt[t] * m.Pload / 1000 +
            (m.Wt[t] - m.Wcurtt[t]) * (m.Wptc - m.PenWindBasis) / 1000 +
            m.Xt[t] * m.P2t[t] / 1000 -
            m.Gboilt[t] * m.PNGt[t] -  # Boiler fuel cost
            m.Zt[t] * m.P1t[t] / 1000 -
            m.Scurtt[t] * 10.0 / 1000 -
            m.Wcurtt[t] * 10.0 / 1000 -
            m.BDt[t] * m.PenBCA / 1000 -
            m.Lcurtt[t] * m.PenLcurtt / 1000 -
            m.Ct[t] * m.PenNonCFE / 1000
            for t in m.T))
    model.o = pyo.Objective(rule=obj, sense=pyo.maximize)

    ## CONSTRAINTS ##

    # Electricity balance
    # Supply: CleanFirm + imports + wind + solar + BESS discharge + turbine
    # Demand: load + BESS charge + TES charge + curtailment
    def r_electricitybalance(m, t):
        return (m.CleanFirm[t] + m.Zt[t] + m.Wt[t] + m.St[t]
                + m.BDt[t] + m.Gtest[t]
                == m.Lt[t] + m.BCt[t] + m.TCt[t]
                + m.Scurtt[t] + m.Wcurtt[t])
    model.c1 = pyo.Constraint(model.T, rule=r_electricitybalance)

    # Curtailment limits
    def r_limScurtt(m, t):
        return m.Scurtt[t] <= m.St[t]
    model.c2 = pyo.Constraint(model.T, rule=r_limScurtt)

    def r_limWcurtt(m, t):
        return m.Wcurtt[t] <= m.Wt[t]
    model.c3 = pyo.Constraint(model.T, rule=r_limWcurtt)

    # Load constraints
    def r_loadmin(m, t):
        return m.Lt[t] + m.Lcurtt[t] >= m.Lmin
    model.c4 = pyo.Constraint(model.T, rule=r_loadmin)

    def r_loadmax(m, t):
        return m.Lt[t] <= m.Lmax
    model.c5 = pyo.Constraint(model.T, rule=r_loadmax)

    # BESS constraints
    def r_calcBXt(m, t):
        if t == start_time:
            return m.BXt[t] == m.BXi + m.BCt[t] - m.lBt[t] - m.BDt[t]
        return m.BXt[t] == m.BXt[t - 1] + m.BCt[t] - m.lBt[t] - m.BDt[t]
    model.c7 = pyo.Constraint(model.T, rule=r_calcBXt)

    def r_calclBt(m, t):
        return m.lBt[t] == m.BCt[t] * (1 - m.Brte)
    model.c8 = pyo.Constraint(model.T, rule=r_calclBt)

    def r_limBX(m, t):
        return m.BXt[t] <= m.BXmaxt[t]
    model.c9 = pyo.Constraint(model.T, rule=r_limBX)

    def r_limBD(m, t):
        return m.BDt[t] <= m.BessDlim * (1 - m.KBct[t])
    model.c10 = pyo.Constraint(model.T, rule=r_limBD)

    def r_limBC(m, t):
        return m.BCt[t] <= m.BessClim * m.KBct[t]
    model.c11 = pyo.Constraint(model.T, rule=r_limBC)

    # TES constraints
    def r_calclTvt(m, t):
        return m.lTvt[t] == m.TCt[t] * (1 - m.Teff)
    model.c_tes_loss = pyo.Constraint(model.T, rule=r_calclTvt)

    def r_calcTXt(m, t):
        if t == start_time:
            return m.TXt[t] == m.TXi + m.TCt[t] - m.lTvt[t] - m.TDt[t]
        return m.TXt[t] == m.TXt[t - 1] + m.TCt[t] - m.lTvt[t] - m.TDt[t]
    model.c_tes_soc = pyo.Constraint(model.T, rule=r_calcTXt)

    def r_limTXt(m, t):
        return m.TXt[t] <= m.TXmax
    model.c_tes_xmax = pyo.Constraint(model.T, rule=r_limTXt)

    def r_limTCt(m, t):
        return m.TCt[t] <= m.TCmax
    model.c_tes_cmax = pyo.Constraint(model.T, rule=r_limTCt)

    def r_limTDt(m, t):
        return m.TDt[t] <= m.TDmax
    model.c_tes_dmax = pyo.Constraint(model.T, rule=r_limTDt)

    # Boiler constraints
    def r_limBoilt(m, t):
        return m.Boilt[t] <= m.BoilerTmax
    model.c_boiler_max = pyo.Constraint(model.T, rule=r_limBoilt)

    def r_calcGboilt(m, t):
        # Convert thermal output to fuel consumption
        # Boilt is in kW thermal, need MMBTU/hr
        # 1 kW = 0.003412 MMBTU/hr
        return m.Gboilt[t] == m.Boilt[t] * 0.003412 / m.BoilerEff
    model.c_boiler_fuel = pyo.Constraint(model.T, rule=r_calcGboilt)

    # Steam header balance
    # Heat sources: TES discharge + Boiler
    def r_steamheader(m, t):
        return m.SThermt[t] == m.TDt[t] + m.Boilt[t]
    model.c_steamheader = pyo.Constraint(model.T, rule=r_steamheader)

    # Steam turbine
    def r_calcGtest(m, t):
        return m.Gtest[t] == m.SThermt[t] * m.GTeff
    model.c_st_eff = pyo.Constraint(model.T, rule=r_calcGtest)

    def r_limT3th(m, t):
        return m.Gtest[t] <= m.T3max
    model.c_st_max = pyo.Constraint(model.T, rule=r_limT3th)

    # Carbon fraction
    def r_calcCt(m, t):
        return m.Ct[t] == m.Boilt[t] * m.GTeff * (1 - m.BoilerFuelCFE) + m.Zt[t] * (1 - m.Gcfet[t])
    model.c18 = pyo.Constraint(model.T, rule=r_calcCt)

    # Import/export limits
    def r_limZt(m, t):
        return m.Zt[t] <= m.impmax
    model.c19 = pyo.Constraint(model.T, rule=r_limZt)

    def r_limXt(m, t):
        return m.Xt[t] <= m.exmax
    model.c20 = pyo.Constraint(model.T, rule=r_limXt)

    # Load ramping
    def r_calc_Lt(m, t):
        if t == start_time:
            return m.Lt[t] == m.Lti + m.dLt[t]
        return m.Lt[t] == m.Lt[t - 1] + m.dLt[t]
    model.c21 = pyo.Constraint(model.T, rule=r_calc_Lt)

    def r_limdLthi(m, t):
        return m.dLt[t] <= m.dLmax
    model.c22 = pyo.Constraint(model.T, rule=r_limdLthi)

    def r_limdLt_lo(m, t):
        return m.dLt[t] >= -1.0 * m.dLmax
    model.c23 = pyo.Constraint(model.T, rule=r_limdLt_lo)

    def r_limLcurtt(m, t):
        return m.Lcurtt[t] <= m.Lmax
    model.c24 = pyo.Constraint(model.T, rule=r_limLcurtt)

    # BESS cycle limit
    def discharge_limit_rule(m):
        return (sum(m.BDt[t] for t in range(start_time, min(start_time + int(vars['step_size']), end_time))) <=
                m.cycle_d_ratio * dfopsx['BXmaxt'].iloc[:(iteration * int(vars['step_size']))].iloc[::24].sum() - tot_dis)
    model.ccycle = pyo.Constraint(rule=discharge_limit_rule)

    ## SOLVE ##
    if vars.get('solve_with_highs', 0) == 1:
        solver = pyo.SolverFactory('appsi_highs')
    elif vars['solve_with_gurobi'] == 1:
        solver = pyo.SolverFactory('gurobi')
        solver.options['MIPGapAbs'] = 1000 * (vars['window_size'] / 36) * (vars['Load_max'] / 250)
    else:
        solver = pyo.SolverFactory('cplex_direct')
        solver.options['mip_tolerances_absmipgap'] = 1000 * (vars['window_size'] / 36) * (vars['Load_max'] / 250)

    if threads:
        if vars['solve_with_gurobi'] == 1:
            solver.options['Threads'] = threads
        elif vars.get('solve_with_highs', 0) != 1:
            solver.options['threads'] = threads

    results = solver.solve(model, tee=False)

    # Extract results
    results_dict = {}
    for v in model.component_objects(pyo.Var, active=True):
        for index in v:
            if index is None:
                results_dict[str(v)] = pyo.value(v)
            else:
                if str(v) not in results_dict:
                    results_dict[str(v)] = {}
                results_dict[str(v)][index] = pyo.value(v[index])

    tot_dis += sum(pyo.value(model.BDt[t]) for t in time[:int(vars['step_size'])])
    num_vars = model.nvariables()
    obj_val = pyo.value(model.o)

    return results_dict, tot_dis, num_vars, obj_val, threads
