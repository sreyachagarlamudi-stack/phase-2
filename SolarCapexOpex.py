"""
Solar Cost Modeling
CapEx and OpEx calculations for solar PV systems
"""
import pandas as pd
import numpy as np

def solarcapex(vars, cdata, n, MWp, MWi, ngsu):
    acres = MWp * vars['gcr'] #grc here is in acres/MWdc
    capex_acre = -acres * cdata.at['capex_pv_$acre', n]
    capex_dc = -MWp * cdata.at['capex_pv_$MWdc', n]
    capex_ac = -MWi * cdata.at['capex_pv_$Mwac', n]
    capex_fixed = -cdata.at['capex_pv_fix', n]
    capex_hv = -MWi * cdata.at['capex_HV_$Mwac', n]
    capex_gsu = - ngsu * cdata.at['capex_HV_$gsu', n]

    capex_module = -MWp * cdata.at['capex_pv_$MWmodules', n]
    capex_pvbos = capex_acre + capex_dc + capex_ac + capex_fixed
    capex_hvbos = capex_hv + capex_gsu
    capex_txbos = -vars['GT1L'] * cdata.at['capex_gt_$mi', n]
    capex_oc = cdata.at['capex_oc', n] * (capex_pvbos + capex_hvbos)

    capex_nonEPCbos = -cdata.at['capex_nonEPCBOS', n]
    capex_devcosts = -cdata.at['capex_devcost', n]

    # construction financing does not include dev costs, only physical costs
    capex_physical = (capex_module + capex_pvbos + capex_hvbos + capex_txbos + capex_oc + capex_nonEPCbos)
    capex_financefees = cdata.at['capex_cdebt', n] * capex_physical
    grosscapex = capex_physical + capex_financefees + capex_devcosts

    # TX is not itc eligible
    itc_capex = (grosscapex - capex_txbos*(1+cdata.at['capex_cdebt', n])) * 0.975
    
    return grosscapex, itc_capex

def solaropex(vars, cdata, n, grosscapex, MWp, MWi, yr1rev, yrs):
    opexrows = ['o&m_s_dc', 'o&m_s_ac', 'o&m_s_acre', 'o&m_s_lease', 'o&m_s_pt', 'o&m_s_ins']
    opex = pd.DataFrame(index=opexrows, columns=np.arange(0,yrs+1,1))
    opex.loc[:,:] = 0.0

    opex.at['o&m_s_pt', 0] = grosscapex * cdata.at['opex_pv_pt_y0', n]
    acres = MWp * vars['gcr'] #grc here is in acres/MWdc

    # for ac basis, solar opex is entered as property tax, as % of capex
    if vars['solar_basis']=='AC':
        opex.at['o&m_s_net', 0] = 0
        for y in np.arange(1, yrs+1, 1):
            escfctr = (1+vars['fin_esc'])**(y-1)
            opex.at['o&m_s_net', y] = escfctr * (grosscapex *cdata.at['opex_pv_ins_capex', n])

    else:
        for y in np.arange(1, yrs+1, 1):
            ycal = vars['COD'] + y - 1
            escfctr = (1+vars['fin_esc'])**(y-1)

            # opex, dc #
            c0 = cdata.at['opex_pv_dc_$mw', n]
            if y<=2:
                c1 = 300
            else:
                c1 = 850
            c3 = (1+vars['fin_esc'])**(ycal - cdata.at['opex_pv_refyear', n])
            opex.at['o&m_s_dc', y] = - MWp * ((c0 + c1)*c3 + 1064*c3) - 689000*c3
            # opex, ac. Note - amortized externally so no escalation
            opex.at['o&m_s_ac', y] = - MWi * 1029
            # opex, acres
            opex.at['o&m_s_acre', y] = - c3 * acres * cdata.at['opex_pv_veg_$acre', n]
            # opex, lease
            opex.at['o&m_s_lease', y] = - escfctr * acres * cdata.at['opex_pv_lease_$acre', n]
            # opex property tax
            ystring = 'opex_pv_pt_y' + str(y)
            pty = cdata.at[ystring, n]
            opex.at['o&m_s_pt', y] = grosscapex * pty 
            opex.at['o&m_s_ins', y] = escfctr * (grosscapex *cdata.at['opex_pv_ins_capex', n] -
                                                yr1rev * cdata.at['opex_pv_ins_rev', n])

        
        opex.loc['o&m_s_net', :] = 0.0
        for y in np.arange(0, yrs+1, 1):
            for om in opexrows:
                opex.at['o&m_s_net', y] += opex.at[om,y]

    return np.asarray(opex.loc['o&m_s_net', :])


