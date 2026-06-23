import numpy as np
import pandas as pd
import numpy_financial as npf
import SolarCapexOpex

def build_pfx(vars, svar, opsx, dftotin, basepath, mode):
    ## utilities
    if mode=='Simple' or mode== 'opt':
        qy = vars['yrstorun']
        zf = qy*8760-1
    else:
        zf = 30*8760-1
    
    pfyrs = max(30, vars['proj_life'])+1
    yrs = np.arange(1, pfyrs,1)
        

    ## load data
    # load pro forma template, add columns and initialize all with 0
    pfx = pd.read_excel(basepath + '/Inputs/pftemplate.xlsx', sheet_name='DTC_CPLEX', header=None, index_col=0)
    pfx.loc['v_Lt':'ncf', str(0)]=0.0
    for y in yrs:
        pfx.loc['v_Lt':'ncf', str(y)]=0.0

    # load solar cost data
    if vars['include_solar']:
        scd = pd.read_excel(basepath + '/Inputs/pv_cost_inputs.xlsx', sheet_name=str(vars['solarcost_sheet']), index_col=0)
        if vars['solar_basis'] == 'AC':
            scol = 'ac-simple'
        else:
            scol = vars['solarcost_ref']

    ## initialize for year 0
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

    # wind capex
    if svar['wf_MW']==0 or vars['structure_w']=='Tolled':
        wcapex = 0
    else:
        wcapex = vars['capex_Wfix'] + vars['capex_Wvar'] * svar['wf_MW']
    pfx.at['capex_wind', str(0)] = -wcapex

    # bess capex
    if svar['bess_kWh']==0 or vars['structure_b']=='Tolled':
        bcapex = 0
    else:
        bcapex =  vars['capex_Bvar'] * svar['bess_kWh'] / 1000.0 # price in $/MWh
    pfx.at['capex_B', str(0)] = -bcapex

    # ldes capex
    if svar['ldes_kWh']==0 or vars['structure_l']=='Tolled':
        lcapex = 0
    else:
        lcapex_kw = vars['capex_Ldpwr'] * svar['ldesD_kW'] / 1000.0 # price in $/MW
        lcapex_kwh = vars['capex_Ldvar'] * svar['ldes_kWh'] / 1000.0 # price in $/MWh
        lcapex = lcapex_kw + lcapex_kwh
    pfx.at['capex_Ld', str(0)] = -lcapex

    # ng capex
    if svar['ngMW']==0 or vars['structure_ng']=='Tolled':
        ngcapex = 0
    else:
        ngcapex =  vars['capex_NGvar'] * svar['ngMW'] + (1e6) * vars['capex_pipe']
    pfx.at['capex_NG', str(0)] = -ngcapex

    ## pull operating data
    # simple mode - every year of operations matches the average of the modeled data. TV volumes are based on representative year
    if mode == 'Simple' or mode=='opt':
         # calculate v_TV in dfops
        if vars['structure_s']=='Tolled' and vars['structure_w']=='Tolled':
            opsx['TVkw'] = np.full(vars['total_time'], 0)
        elif vars['structure_s']=='Tolled' and vars['structure_w']=='Integrated':
            if vars['tv_swbasis'] == 'PtX Shape':
                opsx['TVkw'] = np.minimum(np.asarray(opsx['Wt']), svar['loadbasisMW']*1000.0)
            elif vars['tv_swbasis'] == 'Generated':
                opsx['TVkw'] = np.asarray(opsx['Wt'])
        elif vars['structure_s']=='Integrated' and vars['structure_w']=='Tolled':
            if vars['tv_swbasis'] == 'PtX Shape':
                opsx['TVkw'] = np.minimum(np.asarray(opsx['St']), svar['loadbasisMW']*1000.0)
            elif vars['tv_swbasis'] == 'Generated':
                opsx['TVkw'] = np.asarray(opsx['St'])
        else:
            if vars['tv_swbasis'] == 'PtX Shape':
                opsx['TVkw'] = np.minimum(np.asarray(opsx['St'] + opsx['Wt']), svar['loadbasisMW']*1000.0)
            elif vars['tv_swbasis'] == 'Generated':
                opsx['TVkw'] = np.asarray(opsx['St'] + opsx['Wt'])
        for y in yrs:
            if y <= vars['proj_life']:
                # annualize, convert kWh to MWh
                pfx.at['v_St', str(y)] = opsx['St'].sum() / qy / 1000.0
                pfx.at['v_Scurtt', str(y)] = opsx['Scurtt'].sum() / qy / 1000.0
                pfx.at['v_Wt', str(y)] = opsx['Wt'].sum() / qy / 1000.0
                pfx.at['v_Wcurtt', str(y)] = opsx['Wcurtt'].sum() / qy / 1000.0
                pfx.at['v_Wptc', str(y)] = pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]
                pfx.at['v_TV', str(y)] = 0.0
                pfx.at['v_NGt', str(y)] = (opsx['Gt'].sum() * vars['NG_Hrate']) / qy / 1000.0
                pfx.at['v_Gt', str(y)] = opsx['Gt'].sum() / qy / 1000.0
                pfx.at['v_Zt', str(y)] = opsx['Zt'].sum() / qy / 1000.0
                pfx.at['v_Xt', str(y)] = opsx['Xt'].sum() / qy / 1000.0
                pfx.at['v_Lt', str(y)] = opsx['Lt'].sum() / qy / 1000.0
                pfx.at['d_ESS', str(y)] = ((opsx.at[zf, 'BXt'] + opsx.at[zf, 'LdXt']) - 
                                    opsx.at[0, 'BXt'] - opsx.at[0, 'LdXt']) / qy / 1000.0
                if svar['bess_kWh'] ==0:
                    pfx.at['B_cycles', str(y)] = 0
                else:
                    pfx.at['B_cycles', str(y)] = (opsx['BDt'].sum() / qy / svar['bess_kWh'])
                if svar['ldes_kWh'] == 0:
                    pfx.at['Ld_cycles', str(y)] = 0
                else:
                    pfx.at['Ld_cycles', str(y)] = (opsx['LdDt'].sum() / qy / svar['ldes_kWh'])

                # add Price and stack replace flag
                if y<=10:
                    ycal = y + vars['COD'] - 1
                    ptcesc = (1+vars['fin_esc'])**(ycal-2023)
                    pfx.at['P_wptc', str(y)] = ptcesc * vars['wind_ptc_2023']
                
         
            # past project life, must just pull St, Wt and calculate v_TV from dftotin
            else:
                pfx.at['v_St', str(y)] = opsx['St'].sum() / qy / 1000.0
                pfx.at['v_Scurtt', str(y)] = 0.0
                pfx.at['v_Wt', str(y)] = opsx['Wt'].sum() / qy / 1000.0
                pfx.at['v_Wcurtt', str(y)] = 0.0
                pfx.at['v_TV', str(y)] = opsx['TVkw'].sum() / qy / 1000.0

    # detailed mode 
    else:
        # calculate v_TV in dftotin
        if vars['structure_s']=='Tolled' and vars['structure_w']=='Tolled':
            dftotin['TVkw'] = np.full(vars['total_time'], 0)
        elif vars['structure_s']=='Tolled' and vars['structure_w']=='Integrated':
            if vars['tv_swbasis'] == 'PtX Shape':
                dftotin['TVkw'] = np.asarray(dftotin['Wt'])
            elif vars['tv_swbasis'] == 'Generated':
                dftotin['TVkw'] = np.asarray(dftotin['Wt'])
        elif vars['structure_s']=='Integrated' and vars['structure_w']=='Tolled':
            if vars['tv_swbasis'] == 'PtX Shape':
                dftotin['TVkw'] = np.minimum(np.asarray(dftotin['St']), svar['loadbasisMW']*1000.0)
            elif vars['tv_swbasis'] == 'Generated':
                dftotin['TVkw'] = np.asarray(dftotin['St'])
        else:
            if vars['tv_swbasis'] == 'PtX Shape':
                dftotin['TVkw'] = np.minimum(np.asarray(dftotin['St'] + dftotin['Wt']), svar['loadbasisMW']*1000.0)
            elif vars['tv_swbasis'] == 'Generated':
                dftotin['TVkw'] = np.asarray(dftotin['St'] + dftotin['Wt'])
        for y in yrs:
            # for main project life, must pull from respective year of ops data. 
            if y <= vars['proj_life']:
                y0 = (y-1)*8760
                y1 = y0 + 8759
                pfx.at['v_St', str(y)] = opsx.loc[y0:y1, 'St'].sum() / 1000.0
                pfx.at['v_Scurtt', str(y)] = opsx.loc[y0:y1, 'Scurtt'].sum() / 1000.0
                pfx.at['v_SBFt', str(y)] = opsx.loc[y0:y1, 'SBFt'].sum() / 1000.0
                pfx.at['v_Wt', str(y)] = opsx.loc[y0:y1, 'Wt'].sum() / 1000.0
                pfx.at['v_Wcurtt', str(y)] = opsx.loc[y0:y1, 'Wcurtt'].sum() / 1000.0
                pfx.at['v_Wptc', str(y)] = pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]
                pfx.at['v_TV', str(y)] = 0.0
                pfx.at['v_Gt', str(y)] = opsx.loc[y0:y1, 'Gt'].sum() / 1000.0
                pfx.at['v_NGt', str(y)] = (vars['NG_Hrate'] * opsx.loc[y0:y1, 'Gt'].sum()) / 1000.0
                pfx.at['v_Xt', str(y)] = opsx.loc[y0:y1, 'Xt'].sum() / 1000.0
                pfx.at['v_Zt', str(y)] = opsx.loc[y0:y1, 'Zt'].sum() / 1000.0
                pfx.at['v_Lt', str(y)] = opsx.loc[y0:y1, 'Lt'].sum() /  1000.0
                pfx.at['d_ESS', str(y)] = ((opsx.at[y1, 'BXt'] + opsx.at[y1, 'LdXt']) - 
                                    opsx.at[y0, 'BXt'] - opsx.at[y0, 'LdXt']) / 1000.0
                if svar['bess_kWh']==0:
                    pfx.at['B_cycles', str(y)] = 0
                else:
                    pfx.at['B_cycles', str(y)] = (opsx.loc[y0:y1, 'BDt'].sum()) / svar['bess_kWh']
                if svar['ldes_kWh']==0:
                    pfx.at['Ld_cycles', str(y)] = 0
                else:
                    pfx.at['Ld_cycles', str(y)] = (opsx.loc[y0:y1, 'LdDt'].sum()) / svar['ldes_kWh']

                # add Price and stack replace flag
                if y<=10:
                    ycal = y + vars['COD'] - 1
                    ptcesc = (1+vars['fin_esc'])**(ycal-2023)
                    pfx.at['P_wptc', str(y)] = ptcesc * vars['wind_ptc_2023']
                

            # past project life, must just pull St, Wt and calculate v_TV from dftotin
            else:
                y0 = (y-1)*8760
                y1 = y0 + 8759
                pfx.at['v_St', str(y)] = dftotin.loc[y0:y1, 'St'].sum() / 1000.0
                pfx.at['v_Scurtt', str(y)] = 0.0
                pfx.at['v_Wt', str(y)] = dftotin.loc[y0:y1, 'Wt'].sum() / 1000.0
                pfx.at['v_Wcurtt', str(y)] = 0.0
                pfx.at['v_TV', str(y)] = dftotin.loc[y0:y1, 'TVkw'].sum() / 1000.0
    
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
        solaryrs = max(30, vars['proj_life'])
        if vars['solar_basis'] == 'AC':
            pfx.loc['o&m_solar', str(0):str(max(yrs))] = SolarCapexOpex.solaropex(vars=vars,
                                                                cdata=scd,
                                                                n = scol,
                                                                grosscapex=scapex,
                                                                MWp=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                                MWi=svar['sf_MW'], # ac basis doesn't have granularity on ac vs dc, it just needs MWi = MWac
                                                                yr1rev=yr1rev,
                                                                yrs=solaryrs)
                                                        
        else:
            pfx.loc['o&m_solar', str(0):str(max(yrs))] = SolarCapexOpex.solaropex(vars=vars,
                                                                cdata=scd,
                                                                n = scol,
                                                                grosscapex=scapex,
                                                                MWp=svar['sf_MW'],
                                                                MWi=svar['sf_MWi'],
                                                                yr1rev=yr1rev,
                                                                yrs=solaryrs)
    
    # wind opex - applies over all years, for both simple and detailed
    if svar['wf_MW']==0:
        pass
    elif vars['structure_s'] == 'Tolled':
        for y in np.arange(1, vars['proj_life']+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['ppa_wind', str(y)] = -escfctr * pfx.at['v_Wt', str(y)] * vars['toll_w']
    else:
        for y in yrs:
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['o&m_wind', str(y)] = escfctr * vars['opex_Wvar'] * pfx.at['capex_wind', str(0)]

    # bess opex
    if svar['bess_kWh']==0:
        pass
    # toll applies just for project life
    elif vars['structure_b']=='Tolled':
        for y in np.arange(1, vars['proj_life']+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['toll_bess', str(y)] = -escfctr * svar['bessD_kW'] * vars['toll_b'] * 12.0
    # opex applies for min(bess life, project life)
    else:
        for y in np.arange(1, min(vars['life_B'], vars['proj_life'])+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['o&m_B', str(y)] = escfctr * (-1*vars['opex_Bfix']*svar['bess_kWh']/1000.0)
    
    # ldes opex 
    if svar['ldes_kWh']==0:
        pass
    # toll applies just for project life
    elif vars['structure_l']=='Tolled':
        for y in np.arange(1, vars['proj_life']+1,1):
            
            pfx.at['toll_ldes', str(y)] = -escfctr * svar['ldesD_kW'] * vars['toll_l'] * 12.0
    # opex applies for min(ldes life, project life)
    else:
        for y in np.arange(1, min(vars['life_Ld'], vars['proj_life'])+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['o&m_Ld', str(y)] = escfctr * (-1*vars['opex_Ldfix']*svar['ldes_kWh']/1000.0)
    
    # ng opex 
    if svar['ngMW']==0:
        pass
    # toll applies for all years up to ng life
    elif vars['structure_ng']=='Tolled':
        for y in np.arange(1, vars['proj_life']+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['toll_ng', str(y)] = -escfctr * (svar['ngMW'] * vars['toll_ng'] * 12.0 * 1000.0)
    # opex applies for min(ldes life, project life)
    else:
        for y in np.arange(1, min(vars['life_ng'], vars['proj_life'])+1,1):
            escfctr = (1+vars['fin_esc']) ** (y-1)
            pfx.at['o&m_NG', str(y)] = escfctr * (vars['opex_NGvar']*pfx.at['capex_NG', str(0)] - 
                                                  vars['opex_NGfix']*svar['ngMW'])

    # other items that only occur during project life, even in detailed mode
    for y in np.arange(1, vars['proj_life']+1,1):
        escfctr = (1+vars['fin_esc']) ** (y-1)
        y0 = (y-1)*8760
        y1 = y0 + 8759
        # rev Xt (not escalated for detailed mode, annualized in simple mode)
        if mode=='Detailed': 
            pfx.at['rev_Xt', str(y)] = np.asarray(opsx.loc[y0:y1, 'Xt'] * opsx.loc[y0:y1, 'P2']).sum() / 1000.0
        else:
            pfx.at['rev_Xt', str(y)] = escfctr * np.asarray(opsx['Xt'] * opsx['P2']).sum() / 1000.0 / qy
        # rev RA
        pfx.at['rev_RA', str(y)] = escfctr * 12 * (svar['bessD_kW']*vars['bess_ra'] + 
                                                   svar['ldesD_kW']*vars['ldes_ra'] +
                                                   svar['ngMW']*vars['ng_ra']*1000)
        # opex Zt (not escalated for detailed mode, annualized in simple mode)
        if mode=='Detailed': 
            pfx.at['opex_Zt', str(y)] = - np.asarray(opsx.loc[y0:y1, 'Zt'] * opsx.loc[y0:y1, 'P1']).sum() / 1000.0
        else:
            pfx.at['opex_Zt', str(y)] = - escfctr * np.asarray(opsx['Zt'] * opsx['P1']).sum() / 1000.0 / qy        
        # demand charge - based on max import (just Xt, BCDt not considered)
        if mode=='Detailed': 
            maximport = opsx.loc[y0:y1, 'Zt'].max()
        else:
            maximport = opsx['Zt'].max()
        pfx.at['opex_demandcharge', str(y)] = - escfctr * maximport * vars['demand_charge'] * 12
        # load adder - taken on Lt, Eact, & Eauxt
        pfx.at['opex_loadadder', str(y)] = - escfctr * (pfx.at['v_Lt', str(y)]) * vars['load_adder']
        # GTO premium
        pfx.at['opex_Zt_premium', str(y)] = -escfctr * pfx.at['v_Zt', str(y)] * vars['GTO_premium']
        # Export risk
        pfx.at['opex_Xt_premium', str(y)] = - escfctr * pfx.at['v_Xt', str(y)] * vars['export_premium']
        # Wind Basis
        pfx.at['opex_windbasis', str(y)] = - escfctr * (pfx.at['v_Wt', str(y)] - pfx.at['v_Wcurtt', str(y)]) * vars['wind_basis']
        # opex NGT_fuel 
        if mode=='Detailed':
            # prices for fuel are already in nominal $
            pfx.at['opex_NGt_fuel', str(y)] = - (np.asarray(opsx.loc[y0:y1, 'Gt'] * vars['NG_Hrate'])*opsx.loc[y0:y1, 'PNGt']).sum() / 1000.0
        else:
            # fuel price needs to be annualized and escalated
            pfx.at['opex_NGt_fuel', str(y)] = - escfctr * vars['NG_Hrate']*np.asarray(opsx['Gt']*opsx['PNGt']).sum() / qy / 1000.0
        # opex NGT_VOM
        if mode=='Detailed':
            # prices for fuel are already in nominal $
            pfx.at['opex_NGt_VOM', str(y)] =  - escfctr * pfx.at['v_Gt', str(y)] * vars['opex_NGvom']
        else:
            # fuel price needs to be annualized and escalated
            pfx.at['opex_NGt_VOM', str(y)] = - escfctr * pfx.at['v_Gt', str(y)] * vars['opex_NGvom']

        # opex NGT_firm
        peakdailyrate = svar['ngMW'] * vars['NG_Hrate'] * 24 # in mmbtu/day
        pfx.at['opex_NG_firm', str(y)] = - escfctr * peakdailyrate * vars['NG_firmcost'] * 365
        # pen_ESSdep - positive d_ESS means accumulation, which is not penalized
        pfx.at['pen_ESSdep', str(y)] = escfctr * min(pfx.at['d_ESS', str(y)],0) * vars['ESS_acc_pen']
        # depreciation
        if y<= vars['y_deprec']:
            pfx.at['dep_solar', str(y)] = pfx.at['capex_solar', str(0)] * (1-(0.3+vars['fin_Sitcbonus'])/2) / vars['y_deprec']
            pfx.at['dep_wind', str(y)] = pfx.at['capex_wind', str(0)] / vars['y_deprec']
            pfx.at['dep_B', str(y)] = pfx.at['capex_B', str(0)] * (1-vars['fin_Bitc']/2) / vars['y_deprec']
            pfx.at['dep_Ld', str(y)] = pfx.at['capex_Ld', str(0)] * (1-vars['fin_Lditc']/2) / vars['y_deprec']
        # hard coded 20yr depreciation for NGPP
        if y <= 20:
            pfx.at['dep_NG', str(y)] = pfx.at['capex_NG', str(0)] * (1-vars['itc_NG']/2) / 20 
    # items that only appear after project life (but do not apply if each system is tolled)
    for y in np.arange(vars['proj_life']+1, pfyrs, 1):
        escfctr = (1+vars['fin_esc']) ** (y-1)
        # renewables always have 30yr project life, o&m is already done for full 30yr
        pfx.at['rev_TV_WS', str(y)] = escfctr * pfx.at['v_TV', str(y)] * vars['tv_sw']
        # add bess tv
        if vars['structure_b']=='Integrated' and y<= vars['life_B']:
           pfx.at['rev_TV_B', str(y)] = escfctr * 12 * (vars['tv_bess']*svar['bessD_kW'])
        if vars['structure_l']=='Integrated' and y<= vars['life_Ld']:
             pfx.at['rev_TV_Ld', str(y)] = escfctr * 12 * (vars['tv_ldes']*svar['ldesD_kW'])
        if vars['structure_ng']=='Integrated' and y<=vars['life_ng']:
            pfx.at['rev_TV_NG', str(y)] = escfctr * 12 * (vars['tv_ng']*svar['ngMW']*1000.0)
            
    ## one-offs
    # yr0 ncf
    pfx.at['ncf', str(0)] = pfx.loc['capex_solar':'capex_NG', str(0)].sum() + pfx.at['o&m_solar', str(0)] 

    #solar itc
    if vars['structure_s']=='Integrated':
        pfx.at['itc_solar', str(1)] = - pfx.at['solaritccapex', str(0)] * (0.3 + vars['fin_Sitcbonus']) * vars['fin_tccapture']

    # bess itc
    if vars['structure_b']=='Integrated':
        pfx.at['itc_B', str(1)] = - pfx.at['capex_B', str(0)] * (vars['fin_Bitc']) * vars['fin_tccapture']
    
    # ldes itc
    if vars['structure_l']=='Integrated':
        pfx.at['itc_Ld', str(1)] = - pfx.at['capex_Ld', str(0)] * (vars['fin_Lditc']) * vars['fin_tccapture']

    # ng itc
    if vars['structure_ng']=='Integrated':
        pfx.at['itc_NG', str(1)] = - pfx.at['capex_NG', str(0)] * (vars['itc_NG']) * vars['fin_tccapture']

    # wind and hydrogen ptcs
    for y in np.arange(1,11,1):
        if vars['structure_w'] == 'Integrated':
            pfx.at['ptc_wind', str(y)] = (pfx.at['v_Wptc', str(y)] * pfx.at['P_wptc', str(y)] * 
                                          (1 + vars['fin_Wptcbonus']) * vars['fin_tccapture'])
    return pfx

def calc_npv_irr(vars, pfx, Px):
    pfyrs = max(30, vars['proj_life'])+1

    # complete pro forma
    for y in np.arange(1, pfyrs, 1):
        escfctr = (1+vars['fin_esc']) ** (y-1)
        escfctr_off = (1+vars['fin_esc_offtake']) ** (y-1)
        if y<=vars['proj_life']:
            pfx.at['P_ppa', str(y)] =  escfctr_off*Px
        pfx.at['rev_Lt', str(y)] = pfx.at['v_Lt', str(y)] *  pfx.at['P_ppa', str(y)]

        pfx.at['netrevenue', str(y)] = pfx.loc['rev_Lt':'rev_TV_NG', str(y)].sum()
        pfx.at['netopex', str(y)] = (pfx.loc['o&m_solar':'o&m_NG', str(y)].sum() + 
                                     pfx.loc['ppa_solar':'toll_ng', str(y)].sum() + 
                                     pfx.loc['opex_Zt':'pen_ESSdep', str(y)].sum())
        pfx.at['ebitda', str(y)] = pfx.at['netrevenue', str(y)] + pfx.at['netopex', str(y)]
        pfx.at['netdepreciation', str(y)] = pfx.loc['dep_solar':'dep_NG', str(y)].sum()
        pfx.at['ebit', str(y)] = pfx.at['ebitda', str(y)] + pfx.at['netdepreciation', str(y)]

        if vars['fin_taxefficient'] == 1:
            pfx.at['tax_onpaper', str(y)] = - pfx.at['ebit', str(y)] * vars['fin_taxrate']
            pfx.at['net_income', str(y)] = pfx.at['ebit', str(y)] + pfx.at['tax_onpaper', str(y)]
        else:
            # taxes
            pfx.at['tax_onpaper', str(y)] = - pfx.at['ebit', str(y)] * vars['fin_taxrate']
            if pfx.at['ebit', str(y)] <= 0:
                pfx.at['tax_benefitrealized', str(y)] = 0
                pfx.at['tax_benefitstored', str(y)] = pfx.at['tax_onpaper', str(y)] - pfx.at['tax_benefitrealized', str(y)]
                pfx.at['tax_benefitdeployed', str(y)] = 0
                pfx.at['net_income', str(y)] = pfx.at['ebit', str(y)] + pfx.at['tax_benefitrealized', str(y)]
            else:
                pfx.at['tax_benefitrealized', str(y)] = 0
                pfx.at['tax_benefitstored', str(y)] = 0
                pfx.at['tax_benefitdeployed', str(y)] = min(-pfx.at['tax_onpaper', str(y)], pfx.at['tax_reserve', str(y-1)])
                pfx.at['net_income', str(y)] = pfx.at['ebit', str(y)] + pfx.at['tax_onpaper', str(y)] + pfx.at['tax_benefitdeployed', str(y)]
            pfx.at['tax_reserve', str(y)] = pfx.at['tax_reserve', str(y-1)] + pfx.at['tax_benefitstored', str(y)] - pfx.at['tax_benefitdeployed', str(y)]

        # depreciation add back
        pfx.at['dep_addback', str(y)] = -pfx.at['netdepreciation', str(y)]

        # cash flow
        pfx.at['ncf', str(y)] = (pfx.at['net_income', str(y)] + pfx.at['dep_addback', str(y)] + 
                                 pfx.loc['capex_solar':'capex_NG', str(y)].sum() + 
                                 pfx.loc['itc_solar':'itc_NG', str(y)].sum())

    cashflows = np.asarray(pfx.loc['ncf', :])
    npv = npf.npv(vars['fin_wacc'], cashflows)
    irr = npf.irr(cashflows)

    pfx.at['LCOX', str(0)] = Px
    pfx.at['NPV', str(0)] = npv
    pfx.at['IRR', str(0)] = irr

    return pfx, npv, irr

def calc_lcox(vars, pfxi):
    Pguess = 100
    check = False
    count = 1
    lim = 250*1000

    while check is False and count<= 50:
        # complete proforma and get npv
        pfx, npv, irr = calc_npv_irr(vars=vars, pfx=pfxi, Px=Pguess)

        if abs(npv) <= lim:
            check = True
        else:
            Pguess = Pguess - npv / npf.npv(vars['fin_wacc'], np.asarray(pfx.loc['v_Lt', str(0):str(30)]))
        count += 1
    
    if check == False:
        print('ERROR, LCOX DID NOT CONVERGE')


    return pfx, Pguess
                                                                        
        




