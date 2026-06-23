import numpy as np
import pandas as pd
import numpy_financial as npf
import SolarCapexOpex
import UTILITIES  as util


def build_pfx_v2(vars, svar, opsx, mode, basepath=None):
    """
    vars: dictionary of variable inputs
    svar: dictionary defining system size
    opsx: DataFrame of operating data
    basepath: string of basepath
    mode: string of mode
    """
    
    ### Time Indexing ###
    freq = vars.get('timestep', 1)
    if mode == 'Simple' or mode == 'opt':
        qy = int(vars['yrstorun'])
        
    else:
        qy = int(vars['proj_life'])
    zf = 8760*qy*freq-1
    
    pfyrs = int(max(qy, vars['proj_life']))
    yrs = np.arange(1, pfyrs+1,1)

    ### load utilities ###
    # load pro forma template, add columns and initialize all with 0
    if basepath is None:
        pf_ref_path = 'Inputs/pftemplate.xlsx'
    else:
        pf_ref_path = basepath + '/Inputs/pftemplate.xlsx'
    pfx = pd.read_excel(pf_ref_path , sheet_name='GOOG_Q1_26_V2', header=None, index_col=0)
    pfx.loc['v_Lt':'ncf', str(0)]=0.0
    for y in yrs:
        pfx.loc['v_Lt':'ncf', str(y)]=0.0

    # load solar cost data
    if vars['include_solar']:
        if basepath is None:
            solar_ref_path = 'Inputs/pv_cost_inputs.xlsx'
        else:
            solar_ref_path = basepath + '/Inputs/pv_cost_inputs.xlsx'
        scd = pd.read_excel(solar_ref_path, sheet_name=str(vars['solarcost_sheet']), index_col=0)
        if vars['solar_basis']=='AC':
            scol = 'ac-simple'
        else:
            scol = vars['solarcost_ref']
        
    ### initialize for year 0 ###
    # solar capex
    if svar['sf_MW']==0 or vars['structure_s']=='Tolled':
        scapex=0
        sitccapex=0
    else:
        if vars['solar_basis']=='AC':
            scapex, sitccapex = SolarCapexOpex.solarcapex(vars=vars,
                                                cdata = scd,
                                                n= scol,
                                                MWp=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                MWi=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                ngsu=svar['ngsu']
                                                )
        else:
            scapex, sitccapex = SolarCapexOpex.solarcapex(vars=vars,
                                            cdata = scd,
                                            n= scol,
                                            MWp= svar['sf_MW'],
                                            MWi=svar['sf_MWi'],
                                            ngsu=svar['ngsu']
                                            )
    pfx.at['capex_solar', str(0)] = scapex
    pfx.at['solaritccapex', str(0)] = sitccapex
    pfx.at['capex_solar_ctg', str(0)] = scapex * vars['ctg_solar_capex']
    pfx.at['solaritccapex_ctg', str(0)] = sitccapex * vars['ctg_solar_capex']
    
    # wind capex
    if svar['wf_MW']==0 or vars['structure_w']=='Tolled':
        wcapex = 0
    else:
        wcapex = vars['capex_Wfix'] + vars['capex_Wvar'] * svar['wf_MW']
    pfx.at['capex_wind', str(0)] = -wcapex
    pfx.at['capex_wind_ctg', str(0)] = -wcapex * vars['ctg_wind_capex']

    # bess capex
    if svar['bess_kWh']==0 or vars['structure_b']=='Tolled':
        bcapex_main = 0
    else:
        bcapex_main =  vars['capex_Bvar'] * svar['bess_kWh'] / 1000.0 # price in $/MWh
    bcapex_powersystem = vars['ps_bess_pwr_MW'] * vars['ps_bess_dur_hr'] * vars ['ps_capex_var']
    bcapex = bcapex_main + bcapex_powersystem
    pfx.at['capex_bess', str(0)] = -bcapex
    pfx.at['capex_bess_ctg', str(0)] = -bcapex * vars['ctg_bess_capex']

    # ldes capex
    if svar['ldes_kWh']==0 or vars['structure_l']=='Tolled':
        lcapex = 0
    else:
        lcapex_kw = vars['capex_Ldpwr'] * svar['ldesD_kW'] / 1000.0 # price in $/MW
        lcapex_kwh = vars['capex_Ldvar'] * svar['ldes_kWh'] / 1000.0 # price in $/MWh
        lcapex = lcapex_kw + lcapex_kwh
    pfx.at['capex_ldes', str(0)] = -lcapex
    pfx.at['capex_ldes_ctg', str(0)] = -lcapex * vars['ctg_ldes_capex']

    # ng capex
    if svar['ngMW']==0 or vars['structure_ng']=='Tolled':
        ngcapex = 0
    else:
        ngcapex =  vars['G1_q'] * vars['G1_nameplate_kW'] * vars['G1_capex_$kWnameplate'] + \
                   vars['G2_q'] * vars['G2_nameplate_kW'] * vars['G2_capex_$kWnameplate']
    pfx.at['capex_ngpp', str(0)] = -ngcapex
    pfx.at['capex_ngpp_ctg', str(0)] = -ngcapex * vars['ctg_ngpp_capex']

    ## pull operating data
    # simple mode - every year of operations matches the average of the modeled data
    if mode == 'Simple' or mode=='opt':
        for y_raw in yrs:
            y = int(y_raw)
            # annualize, convert from kW on [freq timesteps per hour] to MWh
            pfx.at['v_St', str(y)] = opsx['St'].sum() / qy / freq / 1000.0
            pfx.at['v_Scurtt', str(y)] = opsx['Scurtt'].sum() / qy / freq / 1000.0
            pfx.at['v_Wt', str(y)] = opsx['Wt'].sum() / qy / freq / 1000.0
            pfx.at['v_Wcurtt', str(y)] = opsx['Wcurtt'].sum() / qy / freq / 1000.0
            pfx.at['v_G1t', str(y)] = opsx['G1t'].sum() / qy / freq / 1000.0
            pfx.at['v_G2t', str(y)] = opsx['G2t'].sum() / qy / freq / 1000.0
            pfx.at['v_cleanfirm', str(y)] = opsx['CleanFirm'].sum() / qy / freq / 1000.0
            pfx.at['v_Zt', str(y)] = opsx['Zt'].sum() / qy / freq / 1000.0
            pfx.at['v_Xt', str(y)] = opsx['Xt'].sum() / qy / freq / 1000.0
            pfx.at['v_Lt', str(y)] = opsx['Lt'].sum() / qy / freq / 1000.0
            # gas is in mmbtu/timestep
            pfx.at['v_NGt', str(y)] = opsx['Gngt'].sum() / qy / freq
            # does not need freq adjustment, does need kW -> MWh adjustment
            pfx.at['d_ESS', str(y)] = ((opsx.at[zf, 'BXt'] + opsx.at[zf, 'LdXt']) - 
                                opsx.at[0, 'BXt'] - opsx.at[0, 'LdXt']) / qy / 1000.0 
            # cycle accounting
            if svar['bess_kWh'] ==0:
                pfx.at['B_cycles', str(y)] = 0
            else:
                pfx.at['B_cycles', str(y)] = (opsx['BDt'].sum() / qy / freq / svar['bess_kWh'])
            if svar['ldes_kWh'] == 0:
                pfx.at['Ld_cycles', str(y)] = 0
            else:
                pfx.at['Ld_cycles', str(y)] = (opsx['LdDt'].sum() / qy / freq / svar['ldes_kWh'])
            pfx.at['G1_cycles', str(y)] = 0 # ignored for now. only calculated in UCED (again, for now).
            pfx.at['G2_cycles', str(y)] = 0 # ignored for now. only calculated in UCED (again, for now).

            # wind ptc
            if y <=10 and vars['fin_windptc']==1:
                ycal = y + vars['COD'] - 1
                ptcesc = (1+vars['fin_esc'])**(ycal-2023)
                pfx.at['P_wptc', str(y)] = ptcesc * vars['wind_ptc_2023']
                pfx.at['v_Wptc', str(y)] = pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]

    # detailed mode 
    else:
        for y_raw in yrs:
            y = int(y_raw)
            # for main project life, must pull from respective year of ops data. 
            y0 = (y-1)*8760*freq
            y1 = y0 + 8760*freq - 1

            # annualize, convert from kW on [freq timesteps per hour] to MWh
            pfx.at['v_St', str(y)] = opsx.loc[y0:y1, 'St'].sum() / freq / 1000.0
            pfx.at['v_Scurtt', str(y)] = opsx.loc[y0:y1, 'Scurtt'].sum() / freq / 1000.0
            pfx.at['v_Wt', str(y)] = opsx.loc[y0:y1, 'Wt'].sum() / freq / 1000.0
            pfx.at['v_Wcurtt', str(y)] = opsx.loc[y0:y1, 'Wcurtt'].sum() / freq / 1000.0
            pfx.at['v_G1t', str(y)] = opsx.loc[y0:y1, 'G1t'].sum() / freq / 1000.0
            pfx.at['v_G2t', str(y)] = opsx.loc[y0:y1, 'G2t'].sum() / freq / 1000.0
            pfx.at['v_cleanfirm', str(y)] = opsx.loc[y0:y1, 'CleanFirm'].sum() / freq / 1000.0
            pfx.at['v_Xt', str(y)] = opsx.loc[y0:y1, 'Xt'].sum() / 1000.0
            pfx.at['v_Zt', str(y)] = opsx.loc[y0:y1, 'Zt'].sum() / 1000.0
            pfx.at['v_Lt', str(y)] = opsx.loc[y0:y1, 'Lt'].sum() /  1000.0
            # gas is in mmbtu/timestep
            pfx.at['v_NGt', str(y)] = opsx.loc[y0:y1, 'Gngt'].sum() / freq 
            # does not need freq adjustment, does need kW -> MWh adjustment
            pfx.at['d_ESS', str(y)] = ((opsx.at[y1, 'BXt'] + opsx.at[y1, 'LdXt']) - 
                                opsx.at[y0, 'BXt'] - opsx.at[y0, 'LdXt']) / 1000.0
            if svar['bess_kWh']==0:
                pfx.at['B_cycles', str(y)] = 0
            else:
                pfx.at['B_cycles', str(y)] = (opsx.loc[y0:y1, 'BDt'].sum()) / (freq * svar['bess_kWh'])
            if svar['ldes_kWh']==0:
                pfx.at['Ld_cycles', str(y)] = 0
            else:
                pfx.at['Ld_cycles', str(y)] = (opsx.loc[y0:y1, 'LdDt'].sum()) / (freq * svar['ldes_kWh'])
            pfx.at['G1_cycles', str(y)] = 0 # ignored for now. only calculated in UCED (again, for now).
            pfx.at['G2_cycles', str(y)] = 0 # ignored for now. only calculated in UCED (again, for now).

            # wind ptc
            if y <=10 and vars['fin_windptc']==1:
                ycal = y + vars['COD'] - 1
                ptcesc = (1+vars['fin_esc'])**(ycal-2023)
                pfx.at['P_wptc', str(y)] = ptcesc * vars['wind_ptc_2023']
                pfx.at['v_Wptc', str(y)] = pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]


    ## non-price dependent revenues and opex
    # solar opex is calculated with separate tool
    if svar['sf_MW']==0:
        pass
    elif vars['structure_s'] == 'Tolled':
        for y in np.arange(1, vars['proj_life']+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['ppa_solar', str(y)] = -escfctr * pfx.at['v_St', str(y)] * vars['toll_s']
    else:
        yr1rev = pfx.at['v_St', str(y)] * 40.0 # assume solar electrons are valued at $40/MWh
        if vars['solar_basis'] == 'AC':
            pfx.loc['o&m_solar', str(int(0)):str(int(pfyrs))] = SolarCapexOpex.solaropex(vars=vars,
                                                                cdata=scd,
                                                                n = scol,
                                                                grosscapex=scapex,
                                                                MWp=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                                MWi=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                                yr1rev=yr1rev,
                                                                yrs=pfyrs)
                                                        
        else:
            pfx.loc['o&m_solar', str(int(0)):str(int(pfyrs))] = SolarCapexOpex.solaropex(vars=vars,
                                                                cdata=scd,
                                                                n = scol,
                                                                grosscapex=scapex,
                                                                MWp=svar['sf_MW'],
                                                                MWi=svar['sf_MWi'],
                                                                yr1rev=yr1rev,
                                                                yrs=pfyrs)
        
    # wind opex - applies over all years, for both simple and detailed
    if svar['wf_MW']==0:
        pass
    elif vars['structure_w'] == 'Tolled':
        for y_raw in yrs:
            y = int(y_raw)
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['ppa_wind', str(y)] = -escfctr * pfx.at['v_Wt', str(y)] * vars['toll_w']
    else:
        for y_raw in yrs:
            y = int(y_raw)
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['o&m_wind', str(y)] = escfctr * vars['opex_Wvar'] * pfx.at['capex_wind', str(0)]

    # bess opex
    for y_raw in yrs:
        y = int(y_raw)
        escfctr = (1+vars['fin_esc']) ** (y-1)
        if vars['structure_b'] == 'Tolled':
            pfx.at['toll_bess', str(y)] = -escfctr * svar['bessD_kW'] * vars['toll_b'] * 12.0
            bess_om_main = 0
        else:
            bess_om_main = escfctr * (-1*vars['opex_Bfix']*svar['bess_kWh']/1000.0)   
        bess_om_powersystem = - escfctr * vars['ps_bess_pwr_MW'] * vars['ps_bess_dur_hr'] * vars['ps_opex_fixed']
        pfx.at['o&m_bess', str(y)] = bess_om_main + bess_om_powersystem
        
    # ldes opex 
    if svar['ldes_kWh']==0:
        pass
    for y_raw in yrs:
        y = int(y_raw)
        escfctr = (1+vars['fin_esc']) ** (y-1)
        if vars['structure_l'] == 'Tolled':
            pfx.at['toll_ldes', str(y)] = -escfctr * svar['ldesD_kW'] * vars['toll_l'] * 12.0
        else:
            pfx.at['o&m_ldes', str(y)] = escfctr * (-1*vars['opex_Ldfix']*svar['ldesD_kW']/1000.0)   
        
    # ng opex 
    if svar['ngMW']==0:
        pass
    for y_raw in yrs:
        y = int(y_raw)
        escfctr = (1+vars['fin_esc']) ** (y-1)
        if vars['structure_ng'] == 'Tolled':
            pfx.at['toll_ng', str(y)] = -escfctr * (svar['ngMW'] * vars['toll_ng'] * 12.0 * 1000.0)
        else:
            pfx.at['o&m_ngpp', str(y)] = - escfctr * (vars['G1_opex_fixed']*vars['G1_q']*vars['G1_nameplate_kW'] + 
                                                vars['G2_opex_fixed']*vars['G2_q']*vars['G2_nameplate_kW'])

    # other items
    for y_raw in yrs:
        y = int(y_raw)
        escfctr = (1+vars['fin_esc']) ** (y-1)
        y0 = (y-1)*8760*freq
        y1 = y0 + 8760*freq - 1

        # cleanfirm opex
        pfx.at['opex_cleanfirm', str(y)] = -escfctr * pfx.at['v_cleanfirm', str(y)] * vars['cleanfirm_cost']

        # rev Xt (not escalated for detailed mode, annualized in simple mode)
        if mode=='Detailed': 
            pfx.at['rev_Xt', str(y)] = np.asarray(opsx.loc[y0:y1, 'Xt'] * opsx.loc[y0:y1, 'P2']).sum() / 1000.0 / freq
        else:
            pfx.at['rev_Xt', str(y)] = escfctr * np.asarray(opsx['Xt'] * opsx['P2']).sum() / 1000.0 / qy / freq
        
        # opex Zt (not escalated for detailed mode, annualized in simple mode)
        if mode=='Detailed': 
            pfx.at['opex_Zt', str(y)] = - np.asarray(opsx.loc[y0:y1, 'Zt'] * opsx.loc[y0:y1, 'P1']).sum() / 1000.0 / freq
        else:
            pfx.at['opex_Zt', str(y)] = - escfctr * np.asarray(opsx['Zt'] * opsx['P1']).sum() / 1000.0 / qy / freq        
        
        # demand charge - based on max import (just Xt, BCDt not considered)
        if mode=='Detailed': 
            maximport = opsx.loc[y0:y1, 'Zt'].max()
        else:
            maximport = opsx['Zt'].max()
        pfx.at['opex_demandcharge', str(y)] = - escfctr * maximport * vars['demand_charge'] * 12
        
        # load adder - taken on Lt, Eact, & Eauxt
        pfx.at['opex_loadadder', str(y)] = - escfctr * (pfx.at['v_Lt', str(y)]) * vars['load_adder']
        
        # Grid import premium
        pfx.at['opex_Zt_premium', str(y)] = -escfctr * pfx.at['v_Zt', str(y)] * vars['import_premium']
        
        # Grid export reduction
        pfx.at['opex_Xt_premium', str(y)] = - escfctr * pfx.at['v_Xt', str(y)] * vars['export_reduction']
        
        # Wind Basis
        pfx.at['opex_windbasis', str(y)] = - escfctr * (pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]) * vars['wind_basis']
        
        # opex NGT_fuel 
        if mode=='Detailed':
            # prices for fuel are already in nominal $
            pfx.at['opex_NGt_fuel', str(y)] = - (opsx.loc[y0:y1, 'Gngt']*opsx.loc[y0:y1, 'PNGt']).sum() / freq
        else:
            # fuel price needs to be annualized and escalated
            pfx.at['opex_NGt_fuel', str(y)] = - escfctr * (opsx['Gngt']*opsx['PNGt']).sum() / qy / freq
        
        # opex NGT_VOM
        pfx.at['opex_NGt_VOM', str(y)] =  - escfctr * (pfx.at['v_G1t', str(y)] * vars['G1_opex_vom'] + pfx.at['v_G2t', str(y)] * vars['G2_opex_vom'])

        # opex NG cycles
        pfx.at['opex_NGt_cycles', str(y)] =  - escfctr * (pfx.at['G1_cycles', str(y)] * vars['G1_cyclecost'] + pfx.at['G2_cycles', str(y)] * vars['G2_cyclecost'])

        # opex NGT_firm
        peakdailyrate = vars['Load_max'] *vars['FT_heatrate_basis'] * 24 # in mmbtu/day
        pfx.at['opex_NG_firm', str(y)] = - escfctr * peakdailyrate * vars['NG_firmcost'] * 365

        # pen_ESSdep - positive d_ESS means accumulation, which is not penalized
        pfx.at['pen_ESSdep', str(y)] = escfctr * min(pfx.at['d_ESS', str(y)],0) * vars['ESS_acc_pen']

        # depreciation
        # Note this is hard coded to 5yr macrs for renewables, 20yr macrs for ngpp
        macrs5yr = util.get_depreciation_list('5yrMACRS')
        macrs20yr = util.get_depreciation_list('20yrMACRS')
        if y<= 6:
            pfx.at['dep_solar', str(y)] = pfx.at['capex_solar', str(0)] * (1-(vars['fin_solaritc'] * vars['fin_solaritcfrac'])/2) * macrs5yr[y-1]
            pfx.at['dep_wind', str(y)] = pfx.at['capex_wind', str(0)] * (1-(vars['fin_winditc'] * vars['fin_winditcfrac'])/2) * macrs5yr[y-1]
            pfx.at['dep_bess', str(y)] = pfx.at['capex_bess', str(0)] * (1-(vars['fin_bessitc'] * vars['fin_bessitcfrac'])/2) * macrs5yr[y-1]
            pfx.at['dep_ldes', str(y)] = pfx.at['capex_ldes', str(0)] * (1-(vars['fin_ldesitc'] * vars['fin_ldesitcfrac'])/2) * macrs5yr[y-1]
        # hard coded 20yr depreciation for NGPP
        if y <= 21:
            pfx.at['dep_ngpp', str(y)] = pfx.at['capex_ngpp', str(0)] * (1-(vars['fin_ngppitc'] * vars['fin_ngppitcfrac'])/2) * macrs20yr[y-1]
        # add ctg depreciation
        pfx.at['dep_solar_ctg', str(y)] = pfx.at['dep_solar', str(y)] * vars['ctg_solar_capex']
        pfx.at['dep_wind_ctg', str(y)] = pfx.at['dep_wind', str(y)] * vars['ctg_wind_capex']
        pfx.at['dep_bess_ctg', str(y)] = pfx.at['dep_bess', str(y)] * vars['ctg_bess_capex']
        pfx.at['dep_ldes_ctg', str(y)] = pfx.at['dep_ldes', str(y)] * vars['ctg_ldes_capex']
        pfx.at['dep_ngpp_ctg', str(y)] = pfx.at['dep_ngpp', str(y)] * vars['ctg_ngpp_capex']

        # depreciation savings
        pfx.at['dep_savings_solar', str(y)] = pfx.at['dep_solar', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_wind', str(y)] = pfx.at['dep_wind', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_bess', str(y)] = pfx.at['dep_bess', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_ldes', str(y)] = pfx.at['dep_ldes', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_ngpp', str(y)] = pfx.at['dep_ngpp', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_solar_ctg', str(y)] = pfx.at['dep_solar_ctg', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_wind_ctg', str(y)] = pfx.at['dep_wind_ctg', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_bess_ctg', str(y)] = pfx.at['dep_bess_ctg', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_ldes_ctg', str(y)] = pfx.at['dep_ldes_ctg', str(y)] * vars['fin_taxrate'] * -1
        pfx.at['dep_savings_ngpp_ctg', str(y)] = pfx.at['dep_ngpp_ctg', str(y)] * vars['fin_taxrate'] * -1

        # wind ptc
        if y <= 10:
            pfx.at['ptc_wind', str(y)] = pfx.at['v_Wptc', str(y)] * pfx.at['P_wptc', str(y)] * vars['fin_windptc']

    #solar itc
    if vars['structure_s']=='Integrated':
        pfx.at['itc_solar', str(0)] = - pfx.at['solaritccapex', str(0)] * (vars['fin_solaritc'] * vars['fin_solaritcfrac']) * vars['fin_tccapture']
        pfx.at['itc_solar_ctg', str(0)] = pfx.at['itc_solar', str(0)] * vars['ctg_solar_capex']

    # bess itc
    if vars['structure_b']=='Integrated':
        pfx.at['itc_bess', str(0)] = - pfx.at['capex_bess', str(0)] * (vars['fin_bessitc'] * vars['fin_bessitcfrac']) * vars['fin_tccapture']
        pfx.at['itc_bess_ctg', str(0)] = pfx.at['itc_bess', str(0)] * vars['ctg_bess_capex']
    
    # ldes itc
    if vars['structure_l']=='Integrated':
        pfx.at['itc_ldes', str(0)] = - pfx.at['capex_ldes', str(0)] * (vars['fin_ldesitc'] * vars['fin_ldesitcfrac']) * vars['fin_tccapture']
        pfx.at['itc_ldes_ctg', str(0)] = pfx.at['itc_ldes', str(0)] * vars['ctg_ldes_capex']

    # ng itc
    if vars['structure_ng']=='Integrated':
        pfx.at['itc_ngpp', str(0)] = - pfx.at['capex_ngpp', str(0)] * (vars['fin_ngppitc'] * vars['fin_ngppitcfrac']) * vars['fin_tccapture']
        pfx.at['itc_ngpp_ctg', str(0)] = pfx.at['itc_ngpp', str(0)] * vars['ctg_ngpp_capex']

    # wind itc/ptc
    if vars['structure_w']=='Integrated':
        pfx.at['itc_wind', str(0)] = - pfx.at['capex_wind', str(0)] * (vars['fin_winditc'] * vars['fin_winditcfrac']) * vars['fin_tccapture']
        pfx.at['itc_wind_ctg', str(0)] = pfx.at['itc_wind', str(0)] * vars['ctg_wind_capex']


    return pfx
                
def complete_pfx_v2(vars, pfx, Px, internal=True):
    pfyrs = int(vars['proj_life'])+1

    # complete pro forma
    for y_raw in np.arange(0, pfyrs, 1):
        y = int(y_raw)
        if y==0:
            escfctr = 0.0
            escfctr_off = 0.0
        else:
            escfctr = (1+vars['fin_esc']) ** (y-1)
            escfctr_off = (1+vars['fin_esc_offtake']) ** (y-1)
        pfx.at['P_ppa', str(y)] =  escfctr_off*Px

        # revenue from offtake ppa
        pfx.at['cf_offtakeppa', str(y)] = pfx.at['v_Lt', str(y)] *  pfx.at['P_ppa', str(y)]
        

        # fill out net costs section
        # calculate net other revenue
        pfx.at['revenues_other', str(y)] = pfx.at['rev_Xt', str(y)]
        # solar opex + ctg
        pfx.at['opex_solar', str(y)] = pfx.loc['o&m_solar':'ppa_solar', str(y)].sum()
        pfx.at['opex_solar_ctg', str(y)] = pfx.at['opex_solar', str(y)] * vars['ctg_solar_opex']
        # wind opex + ctg
        pfx.at['opex_wind', str(y)] = pfx.loc['o&m_wind':'ppa_wind', str(y)].sum()
        pfx.at['opex_wind_ctg', str(y)] = pfx.at['opex_wind', str(y)] * vars['ctg_wind_opex']
        # bess opex + ctg
        pfx.at['opex_bess', str(y)] = pfx.loc['o&m_bess':'toll_bess', str(y)].sum()
        pfx.at['opex_bess_ctg', str(y)] = pfx.at['opex_bess', str(y)] * vars['ctg_bess_opex']
        # ldes opex + ctg
        pfx.at['opex_ldes', str(y)] = pfx.loc['o&m_ldes':'toll_ldes', str(y)].sum()
        pfx.at['opex_ldes_ctg', str(y)] = pfx.at['opex_ldes', str(y)] * vars['ctg_ldes_opex']
        # ngpp opex + ctg
        pfx.at['opex_ngpp', str(y)] = pfx.loc['o&m_ngpp':'opex_NG_firm', str(y)].sum()
        pfx.at['opex_ngpp_ctg', str(y)] = pfx.at['opex_ngpp', str(y)] * vars['ctg_ngpp_opex']
        # system opex + ctg
        pfx.at['opex_system', str(y)] = pfx.loc['opex_Zt':'pen_ESSdep', str(y)].sum()
        pfx.at['opex_system_ctg', str(y)] = pfx.at['opex_system', str(y)] * vars['ctg_system_opex']

        # net opex pre-ctg (net of revenues)
        pfx.at['opex_prectg', str(y)] = pfx.loc['revenues_other':'opex_system', str(y)].sum()
        # net opex ctg
        pfx.at['opex_ctg', str(y)] = pfx.loc['opex_solar_ctg':'opex_system_ctg', str(y)].sum()
        
        ## Tax value components that vary internal vs external methodology
        if internal:
            pfx.at['taxvalue_offtakeppa', str(y)] = 0
            pfx.at['taxvalue_opex_prectg', str(y)] = 0
            pfx.at['taxvalue_opex_ctg', str(y)] = 0
            pfx.at['taxvalue_revenues_other', str(y)] = 0
        else:
            pfx.at['taxvalue_offtakeppa', str(y)] = - pfx.at['cf_offtakeppa', str(y)] * vars['fin_taxrate']
            pfx.at['taxvalue_opex_prectg', str(y)] = - pfx.at['opex_prectg', str(y)] * vars['fin_taxrate']
            pfx.at['taxvalue_opex_ctg', str(y)] = - pfx.at['opex_ctg', str(y)] * vars['fin_taxrate']
            pfx.at['taxvalue_revenues_other', str(y)] = - pfx.at['revenues_other', str(y)] * vars['fin_taxrate']

        # calculate net costs
        pfx.at['netcosts', str(y)] = (pfx.at['opex_prectg', str(y)] + pfx.at['opex_ctg', str(y)] + 
                                         pfx.at['taxvalue_revenues_other', str(y)] + 
                                         pfx.loc['dep_savings_solar':'dep_savings_ngpp_ctg', str(y)].sum() +
                                         pfx.loc['capex_solar':'capex_ngpp_ctg', str(y)].sum() + 
                                            pfx.loc['itc_solar':'itc_ngpp_ctg', str(y)].sum() + 
                                            pfx.loc['taxvalue_opex_prectg', str(y)] + 
                                            pfx.loc['taxvalue_opex_ctg', str(y)])

        # cash flow
        pfx.at['ncf', str(y)] = (pfx.at['netcosts', str(y)] + pfx.at['cf_offtakeppa', str(y)] + pfx.at['taxvalue_offtakeppa', str(y)])

    
            
    proj_life = int(vars['proj_life'])
    cols = [str(y) for y in range(0, proj_life + 1)]

    if internal:
        pfx.at['Discounted Costs', str(0)] = -npf.npv(vars['fin_wacc_internal'], np.asarray(pfx.loc['netcosts', :]))
        pfx.at['Discounted Load', str(0)] = npf.npv(vars['fin_wacc_internal'], np.asarray(pfx.loc['v_Lt', :]))
        pfx.at['NPV', str(0)] = npf.npv(vars['fin_wacc_internal'], np.asarray(pfx.loc['ncf', :]))
        pfx.at['IRR', str(0)] = npf.irr(np.asarray(pfx.loc['ncf', :]))
        # calcualte LCOX
        pfx.at['LCOX', str(0)] = pfx.at['Discounted Costs', str(0)] / pfx.at['Discounted Load', str(0)]
    else:
        pfx.at['Discounted Costs', str(0)] = -npf.npv(vars['fin_wacc_external'], np.asarray(pfx.loc['netcosts', :]))
        pfx.at['Discounted Load', str(0)] = npf.npv(vars['fin_wacc_external'], np.asarray(pfx.loc['v_Lt', :]))
        pfx.at['NPV', str(0)] = npf.npv(vars['fin_wacc_external'], np.asarray(pfx.loc['ncf', :]))
        pfx.at['IRR', str(0)] = npf.irr(np.asarray(pfx.loc['ncf', :]))
        # calcualte new LCOX
        pfx.at['LCOX', str(0)] = pfx.at['Discounted Costs', str(0)] / pfx.at['Discounted Load', str(0)]/(1-vars['fin_taxrate'])

    return pfx


def calc_lcoe(vars, svar, opsx, mode, basepath=None):

    # build pfx shell
    pfx = build_pfx_v2(vars, svar, opsx, mode, basepath=basepath)

    # ### calculate internal LCOE. This does not require iteration (but does get run twice to update all pfx items)
    # # run with Px at arbitrary 100 $/MWh
    # pfx_internal = complete_pfx_v2(vars=vars, pfx=pfx.copy(), Px=100, internal=True)
    # pfx_internal.to_csv('Temp/test_pf_internal.csv')
    # lcoe_internal = pfx_internal.at['LCOX', str(0)]
    # # update pfx with calculated LCOE
    # pfx_internal = complete_pfx_v2(vars=vars, pfx=pfx.copy(), Px=lcoe_internal, internal=True)

    ### calculate internal LCOE via iteration.
    # initial guess of price
    Px = 100
    check = True
    count = 0
    while check and count < 50:
        # build pfx with current price guess
        pfx_internal = complete_pfx_v2(vars=vars, pfx=pfx.copy(), Px=Px, internal=True)
        # check if Px needs to change
        lcoe_new = pfx_internal.at['LCOX', str(0)]
        error = np.abs(lcoe_new - Px)
        if error < 0.01:
            check = False
        else:
            Px = lcoe_new
        count += 1
    if check:
        print('Warning: Internal LCOE did not converge')
    # update internal lcoe value
    lcoe_internal = lcoe_new

    ### calculate external LCOE via iteration.
    # initial guess of price
    Px = 100
    check = True
    count = 0
    while check and count < 50:
        # build pfx with current price guess
        pfx_external = complete_pfx_v2(vars=vars, pfx=pfx.copy(), Px=Px, internal=False)
        # check if Px needs to change
        lcoe_new = pfx_external.at['LCOX', str(0)]
        error = np.abs(lcoe_new - Px)
        if error < 0.01:
            check = False
        else:
            Px = lcoe_new
        count += 1
    if check:
        print('Warning: External LCOE did not converge')
    # update external lcoe value
    lcoe_external = lcoe_new

    return pfx_internal, pfx_external, lcoe_internal, lcoe_external
                                                                        
        




