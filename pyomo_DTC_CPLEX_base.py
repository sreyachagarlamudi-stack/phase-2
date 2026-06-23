"""
Base DTC Dispatch Optimization Module
Rolling window optimization for datacenter CFE with BESS/LDES
"""
import pyomo.environ as pyo
import pandas as pd
import numpy as np
import os
from tqdm import tqdm

def roll_cfe(vars, dfopsx, svar, threads=None, P=200, pos=0):
    # select pyomo logic to use
    pymodel = py_dtc_cfe

    # initialize results dataframe 
    final_results = pd.DataFrame()
    final_results.index.name = 'Hour'
    int_value = []
    i = 0

    # set up rolling window
    window_size = int(vars['window_size'])
    step_size = int(vars['step_size'])
    num_hours = int(vars['dispatch_time'])

    # bess cycle counting
    iteration = 0

    # set up tqdm progress bar
    if threads:
        pbar = tqdm(range(0, num_hours - step_size + 1, step_size), 
                desc=f"Core {pos}", 
                position=pos,
                leave=False)
    else:
        pbar = tqdm(range(0, num_hours - step_size + 1, step_size), desc="Running Model")
    for start in pbar:

        #for start in range(0, num_hours - window_size + 1, step_size):
            if start == 0:
                end = start + window_size

                BX_init = svar['bess_kWh'] * vars['ess_soci']
                LdX_init = svar['ldes_kWh'] * vars['ess_soci']
                Lt_init = vars['Load_max']*1000

                tot_dis = 0
                iteration +=1

                results, tot_dis, num_vars, obj_val, threads = pymodel(vars= vars,
                                    dfopsx= dfopsx,
                                    start_time= start,
                                    end_time= end,
                                    svar= svar,
                                    BX_i= BX_init,
                                    LdX_i= LdX_init,
                                    Lti = Lt_init,
                                    P=P ,
                                    tot_dis=tot_dis,
                                    iteration=iteration,
                                    threads=threads,
                                    )
                pbar.set_postfix(vars=num_vars, obj=f"{obj_val:,.0f}", threads=threads)

                # Convert results to DataFrame
                df_window = pd.DataFrame(results, index=range(start, end))

                # Append to final results
                df_results_step = df_window.iloc[:step_size]
                int_value.append(df_results_step)

            #elif 0 < start <= num_hours - window_size - step_size:
            elif 0 < start <= num_hours - window_size - 1:
                end = start + window_size

                BX_init = int_value[i]['BXt'][start-1]
                LdX_init = int_value[i]['LdXt'][start-1]
                Lt_init = int_value[i]['Lt'][start-1]

                iteration += 1

                results, tot_dis, num_vars, obj_val, threads = pymodel(vars= vars,
                                    dfopsx= dfopsx,
                                    start_time= start,
                                    end_time= end,
                                    svar= svar,
                                    BX_i= BX_init,
                                    LdX_i= LdX_init,
                                    Lti = Lt_init,
                                    P=P ,
                                    tot_dis=tot_dis,
                                    iteration=iteration,
                                    threads=threads,
                                    )
                pbar.set_postfix(vars=num_vars, obj=f"{obj_val:,.0f}", threads=threads)

                # Convert results to DataFrame
                df_window = pd.DataFrame(results, index=range(start, end))

                # Append to final results
                df_results_step = df_window.iloc[:step_size]
                int_value.append(df_results_step)
                i += 1

            else :
                end = num_hours

                BX_init = int_value[i]['BXt'][start-1]
                LdX_init = int_value[i]['LdXt'][start-1]
                Lt_init = int_value[i]['Lt'][start-1]

                #iteration += 2
                iteration += 1

                results, tot_dis, num_vars, obj_val, threads = pymodel(vars= vars,
                                    dfopsx= dfopsx,
                                    start_time= start,
                                    end_time= end,
                                    svar= svar,
                                    BX_i= BX_init,
                                    LdX_i= LdX_init,
                                    Lti = Lt_init,
                                    P=P ,
                                    tot_dis=tot_dis,
                                    iteration=iteration,
                                    threads=threads,
                                    )
                pbar.set_postfix(vars=num_vars, obj=f"{obj_val:,.0f}", threads=threads)
                
                # Convert results to DataFrame
                df_window = pd.DataFrame(results, index=range(start, end))

                # Append to final results
                int_value.append(df_window)

                break
             
    final_results = pd.concat(int_value)
    
    return final_results

    
def py_dtc_cfe(vars, dfopsx, start_time, end_time, svar, BX_i, LdX_i, Lti, P, tot_dis, iteration, threads=None):
    time = [i for i in range(start_time, end_time)]

    # Initialize model and parameters
    model = pyo.ConcreteModel()
    # time
    model.T = pyo.Set(initialize=time)
    ## PARAMETERS ##
    # timeseries parameters
    model.P1t = pyo.Param(model.T, initialize={t:dfopsx['P1'][t] for t in time})
    model.P2t = pyo.Param(model.T, initialize={t:dfopsx['P2'][t] for t in time})
    model.Wt = pyo.Param(model.T, initialize={t:dfopsx['Wt'][t] for t in time})
    model.St = pyo.Param(model.T, initialize={t:dfopsx['St'][t] for t in time})
    model.Gcfet = pyo.Param(model.T, initialize={t:dfopsx['CFE'][t] for t in time})
    model.PNGt = pyo.Param(model.T, initialize={t:dfopsx['PNGt'][t] for t in time})
    model.BXmaxt = pyo.Param(model.T, initialize={t:dfopsx['BXmaxt'][t] for t in time})
    model.LdXmaxt = pyo.Param(model.T, initialize={t:dfopsx['LXmaxt'][t] for t in time})
    model.G1maxkWt = pyo.Param(model.T, initialize={t:dfopsx['G1_max_kW'][t] for t in time})
    model.G2maxkWt = pyo.Param(model.T, initialize={t:dfopsx['G2_max_kW'][t] for t in time})
    model.G1hr = pyo.Param(model.T, initialize={t:dfopsx['G1_heatrate_mmbtu_mwh'][t] for t in time})
    model.G2hr = pyo.Param(model.T, initialize={t:dfopsx['G2_heatrate_mmbtu_mwh'][t] for t in time})
    model.CleanFirm = pyo.Param(model.T, initialize={t:(vars['cleanfirm_size']*1000) for t in time})
    # model.Eefft = pyo.Param(model.T, initialize={t:dfopsx['Eefft'][t] for t in time})
    # model.EmaxkWt = pyo.Param(model.T, initialize={t:dfopsx['EmaxkWt'][t] for t in time}) # ????
    #model.escfctr = pyo.Param(model.T, initialize={t:dfopsx['escfctr'][t] for t in time})
    # model.KScurtt = pyo.Param(model.T, initialize={t:dfopsx['KScurtt'][t] for t in time})
    # model.KZt = pyo.Param(model.T, initialize={t:dfopsx['KZt'][t] for t in time})

    # Load parameters
    model.Lmin = pyo.Param(initialize=vars['Load_min']*1000.0) # original is in MW
    model.Lmax = pyo.Param(initialize=vars['Load_max']*1000.0) # original is in MW
    model.dLmax = pyo.Param(initialize=vars['Load_max']*1000.0*vars['Load_MRR']/100.0)
    # power flow constraints
    model.exmax = pyo.Param(initialize=1000*svar['maxExpMW']) 
    model.impmax = pyo.Param(initialize=1000*svar['maxImpMW'])
    # BESS charge.discharge limits
    model.BessDlim = pyo.Param(initialize=svar['bessD_kW']) 
    model.BessClim = pyo.Param(initialize=svar['bessC_kW'])
    model.Brte = pyo.Param(initialize=vars['BESS_rte'])
    # LDES charge/discharge limits
    model.LdesDlim = pyo.Param(initialize=svar['ldesD_kW'])
    model.LdesClim = pyo.Param(initialize=svar['ldesC_kW'])
    model.Lrte = pyo.Param(initialize=vars['LDES_rte'])
    model.Lclr = pyo.Param(initialize=vars['LDES_constantloss']/100.0) # original is a percentage
    model.LdXtarget = pyo.Param(initialize=0.99*dfopsx.loc[start_time:end_time-1, 'LXmaxt'].min())
    model.LdXCbribe = pyo.Param(initialize=15.0)


    # initial ESS conditions
    model.BXi = pyo.Param(initialize=BX_i)
    model.LdXi = pyo.Param(initialize=LdX_i)
    # initial load conditions
    model.Lti = pyo.Param(initialize=Lti)
    # penalties
    model.PenNonCFE = pyo.Param(initialize=vars['NONCFE_pen']) 
    model.PenBCA = pyo.Param(initialize=vars['EA_pen']) 
    model.PenWindBasis = pyo.Param(initialize=vars['wind_basis'])
    model.PenLcurtt = pyo.Param(initialize=vars['Lcurtt_pen'])
    # NG
    model.NGcfe = pyo.Param(initialize=vars['NG_CFE'])
    # NG fuel curve coefficients
    model.G1_fc_bfix = pyo.Param(initialize=vars['G1_fc_bfix'])
    model.G2_fc_bfix = pyo.Param(initialize=vars['G2_fc_bfix'])
    model.G1_fc_mfix = pyo.Param(initialize=vars['G1_fc_mfix'])
    model.G2_fc_mfix = pyo.Param(initialize=vars['G2_fc_mfix'])
    model.G1_fc_bvar = pyo.Param(initialize=vars['G1_fc_bvar'])
    model.G2_fc_bvar = pyo.Param(initialize=vars['G2_fc_bvar'])
    model.G1_fc_mvar = pyo.Param(initialize=vars['G1_fc_mvar'])
    model.G2_fc_mvar = pyo.Param(initialize=vars['G2_fc_mvar'])
    # load / ptc values
    model.Wptc = pyo.Param(initialize=vars['wind_ptc_2023']*((1+vars['fin_esc'])**(vars['COD']-2023)))
    model.Pload = pyo.Param(initialize=P)
    # big m
    model.bigM = pyo.Param(initialize=1e12)
    # bess cycle ratio
    model.cycle_d_ratio = pyo.Param(initialize=vars['BESS_cyclesperyr']/365.0)
    
    ## VARIABLES ##
    # power flows decision variables
    model.Lt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Lcurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.dLt = pyo.Var(model.T, within=pyo.Reals, initialize=0.0)
    model.Scurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Wcurtt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.00)
    model.Zt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.00)
    model.Xt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.00)
    # power flows, BESS
    model.BCt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.BDt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.BXt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.lBt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    # power flows, LDES
    model.LdCt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.LdDt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.LdXt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.lLdt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    # NGPP variables
    model.G1t = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.G2t = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0)
    model.Gngt = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0) 
    
    # BESS state variables
    model.KBct = pyo.Var(model.T, within=pyo.Binary)
    #model.KLdct = pyo.Var(model.T, within=pyo.Binary)
    # fraction carbon based
    model.Ct = pyo.Var(model.T, within=pyo.NonNegativeReals, initialize=0.0) 
    # LDES depletion state
    # model.KdepLdt = pyo.Var(model.T, within=pyo.Binary, initialize=0.0)


    ########################################################################################################

    ## OBJECTIVE FUNCTION ##
    def obj(m):
        return(sum(
                m.Lt[t]*m.Pload/1000 +                                                  
                (m.Wt[t] - m.Wcurtt[t])*(m.Wptc - m.PenWindBasis)/1000 +
                + m.LdCt[t]*m.LdXCbribe/1000 +
                m.Xt[t]*m.P2t[t]/1000 -
                m.Gngt[t]*m.PNGt[t] - # Gngt is in MMBTU
                m.Zt[t]*m.P1t[t]/1000 -
                m.Scurtt[t] * 10.0/1000 -
                m.Wcurtt[t] * 10.0/1000 -
                m.BDt[t] * m.PenBCA/1000 -
                m.Lcurtt[t] * m.PenLcurtt/1000 -
                m.Ct[t]*m.PenNonCFE/1000 for t in m.T) 
                #m.KdepLdt[end_time-1] * (m.LdXtarget - m.LdXt[end_time-1]) * m.LdXCbribe/1000.0       
                )
    model.o = pyo.Objective(rule=obj, sense=pyo.maximize)

    ########################################################################################################

    ## CONSTRAINTS ##
    ## Electricity Balance
    def r_electricitybalance(m, t):
        return (m.CleanFirm[t] + m.Zt[t] + m.Wt[t] + m.St[t] + m.BDt[t] + m.LdDt[t] + m.G1t[t] + m.G2t[t] ==
                m.Lt[t] + m.BCt[t] + m.LdCt[t] + m.Scurtt[t] + m.Wcurtt[t])
    model.c1 = pyo.Constraint(model.T, rule=r_electricitybalance)

    ## Power Flow Rules

    # solar curtailment <= St
    def r_limScurtt(m, t):
        return m.Scurtt[t] <= m.St[t] 
    model.c2 = pyo.Constraint(model.T, rule=r_limScurtt)

    # wind curtailment <= Wt
    def r_limWcurtt(m, t):
        return m.Wcurtt[t] <= m.Wt[t]
    model.c3 = pyo.Constraint(model.T, rule=r_limWcurtt)

    # load min
    def r_loadmin(m, t):
        return m.Lt[t] + m.Lcurtt[t] >= m.Lmin
    model.c4 = pyo.Constraint(model.T, rule=r_loadmin)

    # load max
    def r_loadmax(m, t):
        return m.Lt[t] <= m.Lmax
    model.c5 = pyo.Constraint(model.T, rule=r_loadmax)

    ## NGPP Rules

    def r_limG1t(m, t):
        return m.G1t[t] <= m.G1maxkWt[t]
    model.limG1t = pyo.Constraint(model.T, rule=r_limG1t)

    def r_limG2t(m, t):
        return m.G2t[t] <= m.G2maxkWt[t]
    model.limG2t = pyo.Constraint(model.T, rule=r_limG2t)

    def r_calcGngt(m, t):
        return m.Gngt[t] == m.G1t[t] * m.G1hr[t] / 1000.0 + m.G2t[t] * m.G2hr[t] / 1000.0
    model.r_calcGngt = pyo.Constraint(model.T, rule=r_calcGngt)

    ## BESS Rules

    # BESS SOC
    def r_calcBXt(m, t):
        if t==start_time:
            return m.BXt[t] == m.BXi + m.BCt[t] - m.lBt[t] - m.BDt[t]
        else:
            return m.BXt[t] == m.BXt[t-1] + m.BCt[t] - m.lBt[t] - m.BDt[t]
    model.c7 = pyo.Constraint(model.T, rule=r_calcBXt)

    # Calculate lBt
    def r_calclBt(m, t):
        return m.lBt[t] == m.BCt[t] * (1-m.Brte)
    model.c8 = pyo.Constraint(model.T, rule=r_calclBt)

    # limit BESS SOC
    def r_limBX(m, t):
        return m.BXt[t] <= m.BXmaxt[t]
    model.c9 = pyo.Constraint(model.T, rule=r_limBX)

    # limit BESS D
    def r_limBD(m, t):
        return m.BDt[t] <= m.BessDlim * (1-m.KBct[t])
    model.c10 = pyo.Constraint(model.T, rule=r_limBD)

    # limit BESS C
    def r_limBC(m, t):
        return m.BCt[t] <= m.BessClim * m.KBct[t]
    model.c11 = pyo.Constraint(model.T, rule=r_limBC)

    ## LDES Rules

    # LDES SOC
    def r_calcLdXt(m, t):
        if t==start_time:
            return m.LdXt[t] == m.LdXi + m.LdCt[t] - m.lLdt[t] - m.LdDt[t]
        else:
            return m.LdXt[t] == m.LdXt[t-1] + m.LdCt[t] - m.lLdt[t] - m.LdDt[t]
    model.c12 = pyo.Constraint(model.T, rule=r_calcLdXt) 

    # Calcualte ldes losses
    def r_calclLdt(m, t):
        return m.lLdt[t] == m.LdCt[t] * (1-m.Lrte) + m.LdXt[t] * m.Lclr
    model.c13 = pyo.Constraint(model.T, rule=r_calclLdt)

    # limit SOC
    def r_limLdX(m, t):
        return m.LdXt[t] <= m.LdXmaxt[t]
    model.c14 = pyo.Constraint(model.T, rule=r_limLdX)

    # limit D
    def r_limLdD(m, t):
        return m.LdDt[t] <= m.LdesDlim #* (1-m.KLdct[t])
    model.c15 = pyo.Constraint(model.T, rule=r_limLdD)
    
    # limit C
    def r_limLdC(m, t):
        return m.LdCt[t] <= m.LdesClim #* m.KLdct[t]
    model.c16 = pyo.Constraint(model.T, rule=r_limLdC)

    ## Ct

    # calculate Ct
    def r_calcCt(m, t):
        return m.Ct[t] == (m.G1t[t] + m.G2t[t]) * (1-m.NGcfe) + m.Zt[t] * (1-m.Gcfet[t])
    model.c18 = pyo.Constraint(model.T, rule=r_calcCt)

    # limit Zt
    def r_limZt(m, t):
        return m.Zt[t] <= m.impmax
    model.c19 = pyo.Constraint(model.T, rule=r_limZt)

    # limit Xt
    def r_limXt(m, t):
        return m.Xt[t] <= m.exmax
    model.c20 = pyo.Constraint(model.T, rule=r_limXt)

    # load turndown rules
    def r_calc_Lt(m, t):
        if t==start_time:
            return m.Lt[t] == m.Lti + m.dLt[t]
        else:
            return m.Lt[t] == m.Lt[t-1] + m.dLt[t]
    model.c21 = pyo.Constraint(model.T, rule=r_calc_Lt)

    def r_limdLthi(m, t):
        return m.dLt[t] <= m.dLmax
    model.c22 = pyo.Constraint(model.T, rule=r_limdLthi)

    def r_limdLt_lo(m, t):
        return m.dLt[t] >= -1.0*m.dLmax
    model.c23 = pyo.Constraint(model.T, rule=r_limdLt_lo)

    def r_limLcurtt(m, t):
        return m.Lcurtt[t] <= m.Lmax
    model.c24 = pyo.Constraint(model.T, rule=r_limLcurtt)



    # ## LDES depletion state
    # # calculate Ld depletion state (A): impose K = 0 if Xt > Xi
    # def r_KdepLdt_a(m, t):
    #     return m.LdXt[t] * m.KdepLdt[t] <= m.LdXtarget
    # model.c19 = pyo.Constraint(model.T, rule=r_KdepLdt_a)
    
    # # calculate Ld depletion state (B): impose K = 1 if Xt < Xi
    # def r_KdepLdt_b(m, t):
    #     return m.LdXt[t] + m.KdepLdt[t] * m.bigM >= m.LdXtarget 
    # model.c20 = pyo.Constraint(model.T, rule=r_KdepLdt_b)

    ## BESS cycle count rule
    def discharge_limit_rule(m):
        return (sum(m.BDt[t] for t in range(start_time, min(start_time + int(vars['step_size']), end_time))) <=
                m.cycle_d_ratio * dfopsx['BXmaxt'].iloc[:(iteration * int(vars['step_size']))].iloc[::24].sum() - tot_dis)
    model.ccycle = pyo.Constraint(rule=discharge_limit_rule)


    ########################################################################################################

    ## RUN MODEL ## 
    if vars['solve_with_gurobi']==1:
        solver = pyo.SolverFactory('gurobi')
        solver.options['MIPGapAbs'] = 1000 * (vars['window_size']/36)*(vars['Load_max']/250)
    else:
        solver = pyo.SolverFactory('cplex_direct')
        solver.options['mip_tolerances_absmipgap'] = 1000 * (vars['window_size']/36)*(vars['Load_max']/250)

    

    # Handle thread count
    max_threads = os.cpu_count()
    if threads:
        solver.options['threads'] = min(threads, max_threads)
    
    # results = solver.solve(model, tee=(iteration==1))
    results = solver.solve(model)
    
    
    
    # extract results
    # variables = [
    #     model.P1t, model.P2t, model.P3t, model.Gcfet, model.PNGt,
    #     model.BXmaxt, model.LdXmaxt, model.KZt, 
    #     model.Wt, model.Wcurtt, model.St, model.Scurtt, 
    #     model.GTOt, model.Zt, model.NGt, model.Yot, model.Jot,
    #     model.BCt, model.BDt, model.BXt, model.lB1t, 
    #     model.BCAt,model.BDAt, model.BXAt, model.lB2t, 
    #     model.LdCt, model.LdDt, model.LdXt, model.lLdt,  
    #     model.Lt, model.Ct
    #     ]
    
    variables = [model.Wcurtt, model.Scurtt, model.CleanFirm, model.Zt, model.Xt, \
        model.G1t, model.G2t, model.Gngt, \
        model.BCt, model.BDt, model.BXt, model.lBt, \
        model.LdCt, model.LdDt, model.LdXt, model.lLdt, \
        model.Lt, model.dLt, model.Lcurtt, model.Ct]

    results_dict = {}

    for var in variables:
        var_name = var.name
        if isinstance(var, pyo.Var):
            var_data = var.get_values()
        elif isinstance(var, pyo.Param):
            var_data = {t: var[t] for t in model.T}
        results_dict[var_name] = [var_data[t] for t in model.T]

    # bess cycle counting
    discharge_sum = 0
    for t in range(start_time, min(start_time + int(vars['step_size']), end_time)):
        if t in model.T:
            discharge_sum += model.BDt[t].value

    tot_dis += discharge_sum

    num_vars = sum(len(v) for v in model.component_objects(pyo.Var, active=True))
    obj_val = pyo.value(model.o)
    
    # Get the threads actually used (if set in options, or return max_threads)
    actual_threads = solver.options.get('threads', max_threads)
    
    del model    

    return results_dict, tot_dis, num_vars, obj_val, actual_threads