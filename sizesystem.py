"""
System Sizing
Component capacity calculations for wind, solar, storage, and generation assets
"""
import numpy as np

def sizesystem(vars, sizingvars):
    # size system - basic sizing
    if vars['include_wind']==0:
        wf_MW = 0
    else:
        wf_MW = sizingvars.get('W', 0)
    if vars['include_solar']==0:
        sf_MW = 0
        sf_MWi = 0
    elif vars['solar_basis']=='AC':
        sf_MW = sizingvars.get('S', 0)
        sf_MWi = sizingvars.get('S', 0)
    else:
        sf_MW = sizingvars.get('S', 0)
        sf_MWi = float(sf_MW/sizingvars.get('ILR', 1))
    e_MW = sizingvars.get('E', 0)
    r_kghr = sizingvars.get('r',0)
    t_kg = sizingvars.get('X', 0) * r_kghr

    # PtX plant sizing
    # NH3 - size NH3 plant in tpy, steam turbine in kW, TES X/D/C in kWh & kW
    if vars['product']=='NH3':
        nh3_tpy = sizingvars.get('r', 0) * (8760/1000) * vars['nh3_eff']
        st_kW = nh3_tpy * vars['nh3_st_kW']
        # tes reference size is (max heat to soec electrolyzer) + (max heat to steam turbine)
        maxheat2elect_kW = e_MW * 1000.0 * (vars['elect_maxheat'] / vars['elect_efft0'])
        T_kWh = (st_kW + maxheat2elect_kW) * vars['T_initial']
        TD_kW = T_kWh / vars['tes_duration']
        TC_kW = TD_kW * vars['tes_CDratio']
    # CFE-via-NH3 - size NH3 plant in tpy, steam turbine in kW, no TES
    elif vars['product']=='CFE-via-NH3':
        nh3_tpy = sizingvars.get('r', 0) * (8760/1000) * vars['nh3_eff']
        st_kW = nh3_tpy * vars['nh3_st_kW']
        # tes reference size is (max heat to soec electrolyzer) + (max heat to steam turbine)
        maxheat2elect_kW = e_MW * 1000.0 * (vars['elect_maxheat'] / vars['elect_efft0'])
        T_kWh = 0
        TD_kW = 0
        TC_kW = 0
    else:
        nh3_tpy = 0.0
        st_kW = 0.0
        T_kWh = 0.0
        TC_kW = 0.0
        TD_kW = 0.0

    # loadbasis - for sizing import/export
    # loadbasis is simple load if end product is electricity
    if vars['product'] in ['CFE', 'CFE-CPLEX', 'Mg', 'DTC-CPLEX', 'DTC-SCED-r1']:
        loadbasisMW = vars['Load_max']
    # if end product is LH2, load basis is electrolyzer + LH2
    elif vars['product'] == 'LH2':
        eac_MW =  e_MW *  (vars['elect_maxdc']/100.0) / (1-vars['elect_peloss']/100.0) # size of max ac load
        eaux_MW = e_MW * vars['elect_auxf']/100.0 +  e_MW * (vars['elect_maxdc']/100.0) * (vars['elect_auxv']/100.0)  
        lh2_MW = vars['LH2size'] * (vars['LH2_eff100']/1000)
        loadbasisMW = eac_MW + eaux_MW + lh2_MW
    # for NH3, load basis is electrolyzer + NH3 aux loads
    elif vars['product'] == 'NH3':
        eac_MW =  e_MW * (vars['elect_maxdc']/100.0) / (1-vars['elect_peloss']/100.0) # size of max ac load
        eaux_MW = e_MW * vars['elect_auxf']/100.0 +  e_MW * (vars['elect_maxdc']/100.0) * (vars['elect_auxv']/100.0)
        nh3_aux_f_kW = nh3_tpy * vars['nh3_auxb']  
        nh3_aux_v_kW = sizingvars.get('r', 0) * vars['nh3_eff'] * (1/1000) * vars['nh3_auxm']
        loadbasisMW = eac_MW + eaux_MW + (nh3_aux_f_kW + nh3_aux_v_kW)/1000.0
    # for CFE-via-NH3, load basis is JUST THE PRIMARY LOAD
    elif vars['product'] == 'CFE-via-NH3':
        loadbasisMW = vars['Load_max']

    # size 'solar' gsus - which includes load which is behind pv gsu
    if vars['solar_basis'] == 'AC':
        gsusizetoMW = max(sf_MW, loadbasisMW)
    else:
        gsusizetoMW = max(sf_MWi, loadbasisMW)
    ngsu = np.ceil(gsusizetoMW/vars['pf_gsusize'])
    MWgsu = ngsu * vars['pf_gsusize']

    # ESS sizing
    if vars['include_bess']==0:
        bess_kWh=0
        bessD_kW=0
        bessC_kW=0
    else:
        bess_kWh = sizingvars.get('B', 0) * loadbasisMW * 1000.0
        bessD_kW = bess_kWh / vars['BESS_duration']
        bessC_kW = bessD_kW * vars['BESS_CD_ratio']
    if vars['include_ldes']==0:
        ldes_kWh=0
        ldesC_kW=0
        ldesD_kW=0
    else:
        if vars['product'] == 'DTC-CPLEX':
            ldesD_kW = sizingvars.get('E', 0) * 1000
            ldes_kWh = ldesD_kW * sizingvars.get('X', 0)
            ldesC_kW = ldesD_kW * vars['LDES_CD_ratio']
        else:
            ldes_kWh = sizingvars.get('L', 0) * loadbasisMW * 1000.0
            ldesD_kW = ldes_kWh / vars['LDES_duration']
            ldesC_kW = ldesD_kW * vars['LDES_CD_ratio']
    
    # capacity sizing
    # for electricity end products, capacity is sized to load, and deployed as such
    if vars['product'] in ['CFE', 'CFE-CPLEX', 'Mg', 'DTC-SCED-r1']: 
        if vars['product'] in ['DTC-SCED-r1']:
            fctr = 1.0
        else:
            fctr = 1.025
        if vars['operating_mode'] == 'islanded' or vars['include_capacity'] == 1:
            if vars['size_capacity_to'] == 'min':
                ngMW = vars['Load_min'] * fctr # gross up for losses 
            elif vars['size_capacity_to'] == 'max':
                ngMW = vars['Load_max'] * fctr # gross up for losses 
            elif vars['size_capacity_to'] == 'forced':
                ngMW = vars['forced_capacity'] * fctr # gross up for losses 
        elif vars['include_capacity'] == 0:
            ngMW = 0.0
        else:
             print('ERROR, STRAIGHT TO JAIL.')
             print('BAD CAPACITY SIZING INPUT')
             quit()
    # for DTC-CPLEX, ng size is set by number of unit of each generating class (55-unit-class system, size one unit of each.)
    elif vars['product'] in ['DTC-CPLEX']:
        ngMW = (vars['G1_q'] * vars['G1_nameplate_kW'] + vars['G2_q'] * vars['G2_nameplate_kW'])/1000.0
    ## for other PtX products, the point of capacity is to avoid breaking pyomo dispatch
    # for LH2 end product, capacity is sized for H2 min load and min LH2 plant electricity load
    elif vars['product'] == 'LH2':
            Eacmin = eac_MW * vars['elect_minload']/100.0
            Eauxf = e_MW * vars['elect_auxf']/100.0 # sized to dc load
            Eauxv = (e_MW * vars['elect_minload']/100.0) * (vars['elect_auxv']/100.0) # sized to dc load
            LH2min = (vars['LH2_effmin']/1000.0) * (vars['LH2size'] * vars['LH2_min']/100.0)
            ngMW = (Eacmin + Eauxf + Eauxv + LH2min) 
    # for NH3, capacity is sized for H2 min load and min NH3 plant electrical load
    elif vars['product'] == 'NH3':
        Eacmin = eac_MW * vars['elect_minload']/100.0
        Eauxf = e_MW * vars['elect_auxf']/100.0 # sized to dc load
        Eauxv = (e_MW * vars['elect_minload']/100.0) * (vars['elect_auxv']/100.0) # sized to dc load
        NH3_aux_vmin_kW = nh3_aux_v_kW * vars['nh3_td_min']/100.0
        ngMW = Eacmin + Eauxf + Eauxv + (nh3_aux_f_kW + NH3_aux_vmin_kW)/1000.0
    # for CFE-via-NH3, capacity is sized to the load (either min or max) + h2 min load + min NH3 plant electrical load
    elif vars['product'] == 'CFE-via-NH3':
        eac_MW =  e_MW *  (vars['elect_maxdc']/100.0) / (1-vars['elect_peloss']/100.0) # size of max ac load
        Eacmin = eac_MW * vars['elect_minload']/100.0
        Eauxf = e_MW * vars['elect_auxf']/100.0 # sized to dc load
        Eauxv = (e_MW * vars['elect_minload']/100.0) * (vars['elect_auxv']/100.0) # sized to dc load
        nh3_aux_f_kW = nh3_tpy * vars['nh3_auxb']  
        nh3_aux_v_kW = sizingvars.get('r', 0) * vars['nh3_eff'] * (1/1000) * vars['nh3_auxm']
        NH3_aux_vmin_kW = nh3_aux_v_kW * vars['nh3_td_min']/100.0
        if vars['size_capacity_to']=='min':
            L = vars['Load_min']
        else:
            L = vars['Load_max']
        ngMW = L + Eacmin + Eauxf + Eauxv + (nh3_aux_f_kW + NH3_aux_vmin_kW)/1000.0
  
    # for LH2, size liquid h2 storage
    if vars['product'] == 'LH2':
        LHXkg = vars['LH2size'] * vars['LH2Xhrs']
    else:
        LHXkg = 0

    # for CFE-via-NH3, size initial ammonia inventory
    if vars['product'] == 'CFE-via-NH3':
        # size initial inventory to 500 hrs of min load
        XNi = 2500 * vars['Load_min'] * vars['NG_Hrate'] * (1/17.82) # (hrs) * (MWh/hr) * (MMBTU/MWh) * (MT/MMBTU)
    else:
        XNi = 0.0

    # size max export
    if vars['operating_mode'] == 'islanded' or vars['max_grid_export'] == 'No Export':
        maxExpMW = 0
    elif vars['max_grid_export'] == 'Unconstrained':
        maxExpMW = 1e6
    elif vars['max_grid_export'] == 'Load':
        maxExpMW = loadbasisMW
    elif vars['max_grid_export'] == 'BESS':
        maxExpMW = bessD_kW/1000
    elif vars['max_grid_export'] == 'ESS':
        maxExpMW = (bessD_kW + ldesD_kW)/1000
    elif vars['max_grid_export'] == 'Load + BESS':
        maxExpMW = loadbasisMW + bessD_kW/1000
    elif vars['max_grid_export'] == 'Load + ESS':
        maxExpMW = loadbasisMW + (bessD_kW + ldesD_kW)/1000
    elif vars['max_grid_export'] == 'Load + Capacity':
        maxExpMW = loadbasisMW + ngMW
    elif vars['max_grid_export'] == 'Load + BESS + Capacity':    
        maxExpMW = loadbasisMW + bessD_kW/1000.0 + ngMW
    elif vars['max_grid_export'] == 'Fixed':
        maxExpMW = vars['fixed_export']
    
    # size max import
    if vars['operating_mode'] == 'islanded' or vars['max_grid_import'] == 'No Import' or vars['product'] == 'CFE-via-NH3':
        maxImpMW = 0
    elif vars['max_grid_import'] == 'Unconstrained':
        maxImpMW = 1e6
    elif vars['max_grid_import'] == 'Load':
        maxImpMW = loadbasisMW *1.025 # gross up for losses 
    elif vars['max_grid_import'] == 'BESS':
        maxImpMW = bessC_kW/1000
    elif vars['max_grid_import'] == 'ESS':
        maxImpMW = (bessC_kW + ldesC_kW)/1000
    elif vars['max_grid_import'] == 'Load + BESS':
        maxImpMW = loadbasisMW*1.025 + bessC_kW/1000 # gross up for losses
    elif vars['max_grid_import'] == 'Load + ESS':
        maxImpMW = loadbasisMW*1.025 + (bessC_kW + ldesC_kW)/1000 # gross up for losses
    elif vars['max_grid_import'] == 'Fixed':
        maxImpMW = vars['fixed_export']

    # assemble sizing dictionary
    r = {'wf_MW': float(wf_MW),
         'sf_MW': float(sf_MW),
         'sf_MWi': float(sf_MWi),
         'e_MW': float(e_MW),
         'r_kghr': float(r_kghr),
         't_kg': float(t_kg),
         'bess_kWh': float(bess_kWh),
         'bessD_kW': float(bessD_kW),
         'bessC_kW' : float(bessC_kW),
         'ldes_kWh' : float(ldes_kWh),
         'ldesD_kW' : float(ldesD_kW),
         'ldesC_kW' : float(ldesC_kW),
         'ngMW' : float(ngMW),
         'maxExpMW' : float(maxExpMW),
         'maxImpMW' : float(maxImpMW),
         'ngsu' : ngsu,
         'MWgsu' : float(MWgsu),
         'LHXkg' : float(LHXkg),
         'loadbasisMW' : float(loadbasisMW),
         'NH3_tpy' : float(nh3_tpy),
         'st_kW': float(st_kW),
         'T_kWh': float(T_kWh),
         'TD_kWh':float(TD_kW),
         'TC_kWh':float(TC_kW),
         'XNH3_init':float(XNi)
         }

    return r

def nameconfig(product, sv, vars):
    if product=='LH2':
        cn = ('W' + str(round(sv.get('W', 0),0)) + 'S' + str(round(sv.get('S', 0),0)) + 'I' + str(round(sv.get('ILR', 1),2)) +
              'B' + str(round(sv.get('B', 0),2)) + 'L' + str(round(sv.get('L', 0),2)) + 
              'E' + str(round(sv.get('E', 0),0)) + 'X' + str(round(sv.get('X', 0),2)) + 'r' + str(round(sv.get('r', 0),0)) +
              'LH2_r' + str(round(vars['LH2size'],2)))
    elif product=='NH3':
        cn = ('W' + str(round(sv.get('W', 0),0)) + 'S' + str(round(sv.get('S', 0),0)) + 'I' + str(round(sv.get('ILR', 1),2)) +
              'B' + str(round(sv.get('B', 0),2)) + 'L' + str(round(sv.get('L', 0),2)) + 
               'E' + str(round(sv.get('E', 0),0)) + 'X' + str(round(sv.get('X', 0),2)) + 
               'r' + str(round(sv.get('r', 0),0)))
    elif product in ['CFE', 'CFE-CPLEX', 'Mg']:
        cn = ('W' + str(round(sv.get('W', 0),0)) + 'S' + str(round(sv.get('S', 0),0)) + 'I' + str(round(sv.get('ILR', 1),2)) +
              'B' + str(round(sv.get('B', 0),2)) + 'L' + str(round(sv.get('L', 0),2))+ 'D' + str(round(vars['Load_max'],2)))
    elif product=='CFE-via-NH3':
        cn = ('W' + str(round(sv.get('W', 0),0)) + 'S' + str(round(sv.get('S', 0),0)) + 'I' + str(round(sv.get('ILR', 0),2)) +
                'B' + str(round(sv.get('B', 0),2)) + 'L' + str(round(sv.get('L', 0),2)) + 
                'E' + str(round(sv.get('E', 0),0)) + 'X' + str(round(sv.get('X', 0),2)) + 
                'r' + str(round(sv.get('r', 0),0)) + 'D' + str(round(vars['Load_max'],2)))
    elif product in ['DTC-CPLEX', 'DTC-SCED-r1']:
        cn = ('W' + str(round(sv.get('W',0),0)) + 'S' + str(round(sv.get('S', 0),0)) + 'I' + str(round(sv.get('ILR',1),2)) +
                'B' + str(round(sv.get('B',0),2)) + 'E' + str(round(sv.get('E',0),0)) + 'X' + str(round(sv.get('X',0),2)) + 
                'D' + str(round(vars['Load_max'],2)))
    return cn

