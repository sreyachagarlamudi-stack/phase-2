"""
PtXv3 Core Class
Main optimization class for 24/7 CFE system design and dispatch
Integrates financial modeling, dispatch optimization, and system sizing
"""
import fin_GOOG_Q1_26
import pandas as pd
import numpy as np
import os
import UTILITIES as ut
import pyomo.environ as pyo
import SolarDC2AC
import SolarCapexOpex
import numpy_financial as npf
import pyomo_LH2
import pyomo_NH3
import pyomo_NH3_v2
import pyomo_CFE
import pyomo_CFEviaNH3
import pyomo_CFECPLEXv2
import sizesystem
import fin_LH2
import fin_NH3
import fin_DTC_CPLEX
import fin_GOOG_Q1_26
import fin_NH3_v2
import fin_CFE
import fin_CFEviaNH3
import checks
import optimize
import pyomo_DTC_CPLEX
import xb_CFECPLEX
import pyomo_DTC_SCED_r1


class ptx:
    def __init__(self, df_input, basepath, scenario, dtstr, mode):
        self.df_input = df_input
        self.basepath = basepath
        self.scenario = scenario
        self.dtstr = dtstr

        # load variable list
        self.vars = pd.Series(self.df_input[self.scenario].values, index=self.df_input['VARIABLE']).to_dict()
        
        # include electrolyzer?
        if self.vars['product'] in ['CFE', 'CFE-CPLEX', 'Mg']:
            self.vars['include_elect'] = 0
        else:
            self.vars['include_elect'] = 1

        # simple checks
        check = checks.checks(vars=self.vars, mode=mode)
        if check==False:
            quit()
        
    def build_dfops(self, mode):
        print('Assembling Base dfOps')
        ## mode can be Simple or Detailed ##
        # build dfops shell
        if mode=='Simple' or 'opt':
            self.vars['total_time'] = self.vars['yrstorun']*8760
            self.vars['dispatch_time'] = self.vars['yrstorun']*8760
            self.vars['dfdimyrs'] = self.vars['yrstorun']
        else:
            self.vars['total_time'] = 30*8760
            self.vars['dispatch_time'] = self.vars['proj_life']*8760
            self.vars['dfdimyrs'] = 30

        self.df_tot = pd.DataFrame(index=np.arange(0, self.vars['total_time'],1))

        # load raw timeseries data (prices in nominal)
        df_w = pd.read_csv(self.basepath + '/Data/Wind/' + self.vars['wind_data'] + '.csv')
        df_s = pd.read_csv(self.basepath + '/Data/Solar/' + self.vars['solar_data'] + '.csv')
        df_T = pd.read_csv(self.basepath + '/Data/Temp/' + self.vars['temp_data'] + '.csv') 
        df_P1 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P1_(import)'] + '.csv')
        df_P2 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P2_(export)'] + '.csv')
        df_P3 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P3_(EA)'] + '.csv')
        df_cfe = pd.read_csv(self.basepath + '/Data/CFE/' + self.vars['CFE_grid'] + '.csv')

        # Build NG price dataframe (input curve is assumed to be in nominal $$)
        df_ng = pd.DataFrame(index=np.arange(0, 8760,1))
        if self.vars['include_capacity'] == 0:
            for y in np.arange(1, self.vars['dfdimyrs']+2, 1):
                df_ng[str(y)] = np.full(8760, 0.0)
        else:
            if self.vars['NG_Pbasis'] == 'Fixed':
                for y in np.arange(1, self.vars['dfdimyrs']+2,1): # intentionally add extra column to avoid calling error below
                    df_ng[str(y)] = np.full(8760, self.vars['NG_Pfeed'])
            else:
                df_ng = pd.read_csv(self.basepath + '/Data/NG/' + self.vars['P_NG'] + '.csv')
                for c in df_ng.columns.tolist():
                    df_ng[c] = np.asarray(df_ng.loc[:, c]) 

        # consolidate timeseries into single df
        # for simple mode, ensure that input dataframe dimensions match yrstorun
        # if mode=='Simple':
        #     for d, df in [('W', df_w), ('S',df_s), ('T',df_T), ('P1',df_P1), ('P2',df_P2), ('P3',df_P3),('CFE',df_cfe), ('PNGt', df_ng)]:
        #         if len(df.columns.tolist()) != (1+self.vars['dfdimyrs'] ) and len(df.columns.tolist()) < (1+self.vars['yrstorun']):   
        #             print('WARNING: ', d, ' DIMENSION DOES NOT MATCH DISPATCH yrstorun')
        #             print('DATABASE DIMENSION SMALLER THAN yrstorun')
        #         for y in np.arange(1, self.vars['dfdimyrs'] +1,1):
        #             x0 = (y-1)*8760
        #             x1 = x0 + 8759
        #             self.df_tot.loc[x0:x1, d] = np.asarray(df.loc[:,str(y)])
        # for detailed or opt runs, columns may be different length. for example, you might put aurora curve with solar p50
        # else:
        for d, df in [('W', df_w), ('S',df_s), ('T',df_T), ('P1',df_P1), ('P2',df_P2), ('P3',df_P3),('CFE',df_cfe), ('PNGt', df_ng)]:
                if len(df.columns.tolist()) != (1+self.vars['dfdimyrs'] ) and len(df.columns.tolist()) < (1+self.vars['yrstorun']):   
                    print('WARNING: ', d, ' DIMENSION DOES NOT MATCH DISPATCH yrstorun')
                    print('DATABASE DIMENSION SMALLER THAN yrstorun, REPEATING COLUMNS TO FILL')
                dimdf = len(df.columns.tolist())-1 # number of years in column database
                c = 1
                # retain an extra year in case you start past Q1
                for y in np.arange(1, self.vars['dfdimyrs']+1,1):
                    x0 = (y-1)*8760
                    x1 = x0 + 8759
                    self.df_tot.loc[x0:x1, d] = np.asarray(df.loc[:,str(c)])
                    # repeat input columns as needed to reach desired duration
                    if c==dimdf:
                        c=1
                    else:
                        c+=1
        
        # adjust timeseries start/end based on COD_quarter
        self.df_tot = ut.wrap_shift_monthly(self.df_tot, self.vars['COD_Month'])

        # add solar backfeed cost
        if self.vars['SBF_basis'] == 'ImportPrice':
            self.df_tot['PSBFt'] = self.df_tot['P1']
        else:
            for y in np.arange(1, self.vars['dfdimyrs'] +1,1):
                x0 = (y-1)*8760
                x1 = x0 + 8759
                if mode=='Simple' or mode=='Opt':
                    escrate = 1.0
                else:
                    escrate = (1 + self.vars['fin_esc']) ** (y-1)
                self.df_tot.loc[x0:x1, 'PSBFt'] = np.full(8760, self.vars['SBF_price'] * escrate)
    
        # add degradation states
        # load strips as necessary
        if self.vars['bess_degbasis'] == 'AnnualStrip':
            bessdegstrip = pd.read_csv(self.basepath + '/Data/AnnualStrips/' + self.vars['BESS_deg_strip'] + '.csv', index_col=0)

        if mode == 'Simple':
            # simple mode uses a representative degradation state
            if self.vars['include_solar'] == 0:
                solarstate = 1.0
            else:
                solarstate = (1-self.vars['sdeg']/100.0)**(self.vars['deg_yr_solar']-1)
            self.df_tot['Sstate'] = np.full(self.vars['total_time'], solarstate)
            # bess degradation can be either constant or via strip
            if self.vars['include_bess'] == 0:
                BESSstate = 1.0
            else:
                if self.vars['bess_degbasis'] == 'ConstantRate':
                    BESSstate = (1-self.vars['BESS_deg']/100.0)**(self.vars['deg_yr_ess']-1)
                elif self.vars['bess_degbasis'] == 'AnnualStrip':
                    BESSstate = bessdegstrip.at[self.vars['deg_yr_ess'], 'read']
                else:
                    print('error with BESS degradation input')
            self.df_tot['Bstate'] = np.full(self.vars['total_time'], BESSstate)
            # ldes degradation only has constant loss option
            if self.vars['include_ldes'] == 0:
                LDESstate = 1.0
            else:
                LDESstate = (1-self.vars['LDES_deg']/100.0)**(self.vars['deg_yr_ess']-1)
            self.df_tot['Lstate'] = np.full(self.vars['total_time'], LDESstate)
            if self.vars['include_elect'] ==0:
                electstate = 1.0
            else:
                electstate = (1-8.76*self.vars['elect_deg']/100)**(self.vars['deg_yr_elect']-1)
            self.df_tot['Estate'] = np.full(self.vars['total_time'], electstate)
        else:
            # detailed mode tracks degradation state over time
            # dimension here might include an extra 1-3 quarters to accomodate COD
            dimtemp = len(self.df_tot.index.tolist())
            if self.vars['include_solar'] == 0:
                self.df_tot['Sstate'] = np.full(dimtemp, 1.0)
            else:
                sdegraw = ut.get_deg_curve_constant(self.vars['sdeg']/8760, dimtemp)
                self.df_tot['Sstate'] = np.asarray(sdegraw.loc[0:(dimtemp-1), 'S'])
            if self.vars['include_bess'] == 0:
                self.df_tot['Bstate'] = np.full(dimtemp, 1.0)
            else:
                if self.vars['bess_degbasis'] == 'ConstantRate':
                    BESSdegraw = ut.get_deg_curve_constant(self.vars['BESS_deg']/8760, dimtemp)
                    self.df_tot['Bstate'] = np.asarray(BESSdegraw.loc[0:(dimtemp-1), 'S'])
                elif self.vars['bess_degbasis'] == 'AnnualStrip':
                    striplength = max(bessdegstrip.index.tolist())
                    for y in np.arange(1, self.vars['dfdimyrs']+1, 1):
                        x0 = (y-1)*8760
                        x1 = x0 + 8759
                        if y > self.vars['life_B']:
                            degstatey = 0
                        else:
                            if y == 1:
                                degstatey = 0.5*(1 + bessdegstrip.at[y, 'read'])
                            if y <= striplength:
                                degstatey = 0.5*(bessdegstrip.at[y-1, 'read'] + bessdegstrip.at[y, 'read'])
                            else:
                                degstatey = bessdegstrip.at[striplength, 'read']
                    self.df_tot.loc[x0:x1, 'Bstate'] = np.full(8760, degstatey)
                else:
                    print('error with BESS degradation input')
            # ldes degradataion is constant
            if self.vars['include_ldes'] == 0:
                self.df_tot['Lstate'] = np.full(dimtemp, 1.0)
            else:
                LDESdegraw = ut.get_deg_curve_constant(self.vars['LDES_deg']/8760, dimtemp)
                self.df_tot['Lstate'] = np.asarray(LDESdegraw.loc[0:(dimtemp-1), 'S'])
            if self.vars['include_elect'] == 0:
                self.df_tot['Estate'] = np.full(dimtemp, 1.0)
            else:
                edegraw = ut.get_deg_curve_constant(self.vars['elect_deg']/1000, self.vars['elect_sri']*8760)
                x = 1
                for y in np.arange(1, self.vars['dfdimyrs']+1):
                    y0 = (y-1)*8760
                    y1 = y0+8759
                    x0 = (x-1)*8760
                    x1 = x0+8759
                    self.df_tot.loc[y0:y1, 'Estate'] = np.asarray(edegraw.loc[x0:x1, 'S'])
                    if x==self.vars['elect_sri']:
                        x=1
                    else:
                        x+=1
        
        # escalation factor
        if self.vars['calc_method'] == 'Forecast' or mode=='Detailed':
            escrate = self.vars['fin_esc']
        else:
            escrate=0
        for y in np.arange(1, self.vars['dfdimyrs']+1):
            y0 = (y-1)*8760
            y1 = y0+8759
            self.df_tot.loc[y0:y1, 'escfctr'] = ((1+escrate)**(y-1))

        # add ng escalation and premium
        for y in np.arange(1, self.vars['dfdimyrs']+1,1):
            x0 = (y-1)*8760
            x1 = x0 + 8759 
            if self.vars['NG_Pbasis'] == 'Fixed':
                # prices are in real dollars, premium must also be escalated
                self.df_tot.loc[x0:x1, 'PNGt'] = np.asarray(self.df_tot.loc[x0:x1, 'escfctr'] * (self.df_tot.loc[x0:x1, 'PNGt'] + self.vars['NG_premium']))
            else:
                # base prices are nominal, premium must be escalated
                self.df_tot.loc[x0:x1, 'PNGt'] = np.asarray(self.df_tot.loc[x0:x1, 'PNGt'] + self.df_tot.loc[x0:x1, 'escfctr'] * self.vars['NG_premium'])
        
        # KZt
        self.df_tot['KZt'] = np.where(np.asarray(self.df_tot['P2'])>=np.asarray(self.vars['export_strike']*self.df_tot['escfctr']),
                                      1,
                                      0)
        
        # apply escalation to Price inputs if it's a single column length
        if mode=='Detailed' and len(df_P1.columns.tolist())==2:
            print('Warning: P1 data dimension is 1yr. Escalating for detailed run.')
            self.df_tot['P1'] = np.asarray(self.df_tot['P1']*self.df_tot['escfctr'])
        if mode=='Detailed' and len(df_P2.columns.tolist())==2:
            print('Warning: P2 data dimension is 1yr. Escalating for detailed run.')
            self.df_tot['P2'] = np.asarray(self.df_tot['P2']*self.df_tot['escfctr'])
        if mode=='Detailed' and len(df_P3.columns.tolist())==2:
            print('Warning: P3 data dimension is 1yr. Escalating for detailed run.')
            self.df_tot['P3'] = np.asarray(self.df_tot['P3']*self.df_tot['escfctr'])
            
        self.df_tot.to_csv(self.basepath + 'Temp/dftota.csv')

        return None

    def build_dfops_dtc_cplex(self, mode):
        print('Assembling Base dfOps for DTC-CPLEX')
        ## mode can be Simple or Detailed ##
        # build dfops shell
        if mode=='Simple' or 'opt':
            self.vars['total_time'] = self.vars['yrstorun']*8760
            self.vars['dispatch_time'] = self.vars['yrstorun']*8760
            self.vars['dfdimyrs'] = self.vars['yrstorun']
        else:
            self.vars['total_time'] = 30*8760
            self.vars['dispatch_time'] = self.vars['proj_life']*8760
            self.vars['dfdimyrs'] = 30

        self.df_tot = pd.DataFrame(index=np.arange(0, self.vars['total_time'],1))

        # load raw timeseries data (prices in nominal)
        df_w = pd.read_csv(self.basepath + '/Data/Wind/' + self.vars['wind_data'] + '.csv')
        df_s = pd.read_csv(self.basepath + '/Data/Solar/' + self.vars['solar_data'] + '.csv')
        df_T = pd.read_csv(self.basepath + '/Data/Temp/' + self.vars['temp_data'] + '.csv') 
        df_P1 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P1_(import)'] + '.csv')
        df_P2 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P2_(export)'] + '.csv')
        # dtc-cplex does not need P3
        #df_P3 = pd.read_csv(self.basepath + '/Data/Prices/' + self.vars['P3_(EA)'] + '.csv')
        df_cfe = pd.read_csv(self.basepath + '/Data/CFE/' + self.vars['CFE_grid'] + '.csv')

        # Build NG price dataframe (input curve is assumed to be in nominal $$)
        df_ng = pd.DataFrame(index=np.arange(0, 8760,1))
        if self.vars['include_capacity'] == 0:
            for y in np.arange(1, self.vars['dfdimyrs']+2, 1):
                df_ng[str(y)] = np.full(8760, 0.0)
        else:
            if self.vars['NG_Pbasis'] == 'Fixed':
                for y in np.arange(1, self.vars['dfdimyrs']+2,1): # intentionally add extra column to avoid calling error below
                    df_ng[str(y)] = np.full(8760, self.vars['NG_Pfeed'])
            else:
                df_ng = pd.read_csv(self.basepath + '/Data/NG/' + self.vars['P_NG'] + '.csv')
                for c in df_ng.columns.tolist():
                    df_ng[c] = np.asarray(df_ng.loc[:, c]) 

        # consolidate timeseries into single df
        # for simple mode, ensure that input dataframe dimensions match yrstorun
        # if mode=='Simple':
        #     for d, df in [('W', df_w), ('S',df_s), ('T',df_T), ('P1',df_P1), ('P2',df_P2), ('P3',df_P3),('CFE',df_cfe), ('PNGt', df_ng)]:
        #         if len(df.columns.tolist()) != (1+self.vars['dfdimyrs'] ) and len(df.columns.tolist()) < (1+self.vars['yrstorun']):   
        #             print('WARNING: ', d, ' DIMENSION DOES NOT MATCH DISPATCH yrstorun')
        #             print('DATABASE DIMENSION SMALLER THAN yrstorun')
        #         for y in np.arange(1, self.vars['dfdimyrs'] +1,1):
        #             x0 = (y-1)*8760
        #             x1 = x0 + 8759
        #             self.df_tot.loc[x0:x1, d] = np.asarray(df.loc[:,str(y)])
        # for detailed or opt runs, columns may be different length. for example, you might put aurora curve with solar p50
        # else:
        for d, df in [('W', df_w), ('S',df_s), ('T',df_T), ('P1',df_P1), ('P2',df_P2), ('CFE',df_cfe), ('PNGt', df_ng)]: # cut P3
                if len(df.columns.tolist()) != (1+self.vars['dfdimyrs'] ) and len(df.columns.tolist()) < (1+self.vars['yrstorun']):   
                    print('WARNING: ', d, ' DIMENSION DOES NOT MATCH DISPATCH yrstorun')
                    print('DATABASE DIMENSION SMALLER THAN yrstorun, REPEATING COLUMNS TO FILL')
                dimdf = len(df.columns.tolist())-1 # number of years in column database
                c = 1
                # retain an extra year in case you start past Q1
                for y in np.arange(1, self.vars['dfdimyrs']+1,1):
                    x0 = (y-1)*8760
                    x1 = x0 + 8759
                    self.df_tot.loc[x0:x1, d] = np.asarray(df.loc[:,str(c)])
                    # repeat input columns as needed to reach desired duration
                    if c==dimdf:
                        c=1
                    else:
                        c+=1
        
        # adjust timeseries start/end based on COD_quarter
        self.df_tot = ut.wrap_shift_monthly(self.df_tot, self.vars['COD_Month'])

        # no solar backfeed in DTC-cplex
        # add solar backfeed cost
        # if self.vars['SBF_basis'] == 'ImportPrice':
        #     self.df_tot['PSBFt'] = self.df_tot['P1']
        # else:
        #     for y in np.arange(1, self.vars['dfdimyrs'] +1,1):
        #         x0 = (y-1)*8760
        #         x1 = x0 + 8759
        #         if mode=='Simple' or mode=='Opt':
        #             escrate = 1.0
        #         else:
        #             escrate = (1 + self.vars['fin_esc']) ** (y-1)
        #         self.df_tot.loc[x0:x1, 'PSBFt'] = np.full(8760, self.vars['SBF_price'] * escrate)
    
        # add degradation states
        # load strips as necessary
        if self.vars['bess_degbasis'] == 'AnnualStrip':
            bessdegstrip = pd.read_csv(self.basepath + '/Data/AnnualStrips/' + self.vars['BESS_deg_strip'] + '.csv', index_col=0)

        if mode == 'Simple':
            # simple mode uses a representative degradation state
            if self.vars['include_solar'] == 0:
                solarstate = 1.0
            else:
                solarstate = (1-self.vars['sdeg']/100.0)**(self.vars['deg_yr_solar']-1)
            self.df_tot['Sstate'] = np.full(self.vars['total_time'], solarstate)
            # bess degradation can be either constant or via strip
            if self.vars['include_bess'] == 0:
                BESSstate = 1.0
            else:
                if self.vars['bess_degbasis'] == 'ConstantRate':
                    BESSstate = (1-self.vars['BESS_deg']/100.0)**(self.vars['deg_yr_ess']-1)
                elif self.vars['bess_degbasis'] == 'AnnualStrip':
                    BESSstate = bessdegstrip.at[self.vars['deg_yr_ess'], 'read']
                else:
                    print('error with BESS degradation input')
            self.df_tot['Bstate'] = np.full(self.vars['total_time'], BESSstate)
            # ldes degradation only has constant loss option
            if self.vars['include_ldes'] == 0:
                LDESstate = 1.0
            else:
                LDESstate = (1-self.vars['LDES_deg']/100.0)**(self.vars['deg_yr_ess']-1)
            self.df_tot['Lstate'] = np.full(self.vars['total_time'], LDESstate)
            # no electrolyzer in dtc-cplex
            # if self.vars['include_elect'] ==0:
            #     electstate = 1.0
            # else:
            #     electstate = (1-8.76*self.vars['elect_deg']/100)**(self.vars['deg_yr_elect']-1)
            # self.df_tot['Estate'] = np.full(self.vars['total_time'], electstate)
        else:
            # detailed mode tracks degradation state over time
            # dimension here might include an extra 1-3 quarters to accomodate COD
            dimtemp = len(self.df_tot.index.tolist())
            if self.vars['include_solar'] == 0:
                self.df_tot['Sstate'] = np.full(dimtemp, 1.0)
            else:
                sdegraw = ut.get_deg_curve_constant(self.vars['sdeg']/8760, dimtemp)
                self.df_tot['Sstate'] = np.asarray(sdegraw.loc[0:(dimtemp-1), 'S'])
            if self.vars['include_bess'] == 0:
                self.df_tot['Bstate'] = np.full(dimtemp, 1.0)
            else:
                if self.vars['bess_degbasis'] == 'ConstantRate':
                    BESSdegraw = ut.get_deg_curve_constant(self.vars['BESS_deg']/8760, dimtemp)
                    self.df_tot['Bstate'] = np.asarray(BESSdegraw.loc[0:(dimtemp-1), 'S'])
                elif self.vars['bess_degbasis'] == 'AnnualStrip':
                    striplength = max(bessdegstrip.index.tolist())
                    for y in np.arange(1, self.vars['dfdimyrs']+1, 1):
                        x0 = (y-1)*8760
                        x1 = x0 + 8759
                        if y > self.vars['life_B']:
                            degstatey = 0
                        else:
                            if y == 1:
                                degstatey = 0.5*(1 + bessdegstrip.at[y, 'read'])
                            if y <= striplength:
                                degstatey = 0.5*(bessdegstrip.at[y-1, 'read'] + bessdegstrip.at[y, 'read'])
                            else:
                                degstatey = bessdegstrip.at[striplength, 'read']
                    self.df_tot.loc[x0:x1, 'Bstate'] = np.full(8760, degstatey)
                else:
                    print('error with BESS degradation input')
            # ldes degradataion is constant
            if self.vars['include_ldes'] == 0:
                self.df_tot['Lstate'] = np.full(dimtemp, 1.0)
            else:
                LDESdegraw = ut.get_deg_curve_constant(self.vars['LDES_deg']/8760, dimtemp)
                self.df_tot['Lstate'] = np.asarray(LDESdegraw.loc[0:(dimtemp-1), 'S'])
            # no electrolyzer in dtc-cplex
            # if self.vars['include_elect'] == 0:
            #     self.df_tot['Estate'] = np.full(dimtemp, 1.0)
            # else:
            #     edegraw = ut.get_deg_curve_constant(self.vars['elect_deg']/1000, self.vars['elect_sri']*8760)
            #     x = 1
            #     for y in np.arange(1, self.vars['dfdimyrs']+1):
            #         y0 = (y-1)*8760
            #         y1 = y0+8759
            #         x0 = (x-1)*8760
            #         x1 = x0+8759
            #         self.df_tot.loc[y0:y1, 'Estate'] = np.asarray(edegraw.loc[x0:x1, 'S'])
            #         if x==self.vars['elect_sri']:
            #             x=1
            #         else:
            #             x+=1
        
        # escalation factor
        if self.vars['calc_method'] == 'Forecast' or mode=='Detailed':
            escrate = self.vars['fin_esc']
        else:
            escrate=0
        for y in np.arange(1, self.vars['dfdimyrs']+1):
            y0 = (y-1)*8760
            y1 = y0+8759
            self.df_tot.loc[y0:y1, 'escfctr'] = ((1+escrate)**(y-1))

        # add ng escalation and premium
        for y in np.arange(1, self.vars['dfdimyrs']+1,1):
            x0 = (y-1)*8760
            x1 = x0 + 8759 
            if self.vars['NG_Pbasis'] == 'Fixed':
                # prices are in real dollars, premium must also be escalated
                self.df_tot.loc[x0:x1, 'PNGt'] = np.asarray(self.df_tot.loc[x0:x1, 'escfctr'] * (self.df_tot.loc[x0:x1, 'PNGt'] + self.vars['NG_premium']))
            else:
                # base prices are nominal, premium must be escalated
                self.df_tot.loc[x0:x1, 'PNGt'] = np.asarray(self.df_tot.loc[x0:x1, 'PNGt'] + self.df_tot.loc[x0:x1, 'escfctr'] * self.vars['NG_premium'])
        
        # no need for KZt in dtc-cplex
        # # KZt
        # self.df_tot['KZt'] = np.where(np.asarray(self.df_tot['P2'])>=np.asarray(self.vars['export_strike']*self.df_tot['escfctr']),
        #                               1,
        #                               0)
        
        # apply escalation to Price inputs if it's a single column length
        if mode=='Detailed' and len(df_P1.columns.tolist())==2:
            print('Warning: P1 data dimension is 1yr. Escalating for detailed run.')
            self.df_tot['P1'] = np.asarray(self.df_tot['P1']*self.df_tot['escfctr'])
        if mode=='Detailed' and len(df_P2.columns.tolist())==2:
            print('Warning: P2 data dimension is 1yr. Escalating for detailed run.')
            self.df_tot['P2'] = np.asarray(self.df_tot['P2']*self.df_tot['escfctr'])
        # no P3
        # if mode=='Detailed' and len(df_P3.columns.tolist())==2:
        #     print('Warning: P3 data dimension is 1yr. Escalating for detailed run.')
        #     self.df_tot['P3'] = np.asarray(self.df_tot['P3']*self.df_tot['escfctr'])


        # add ngpp max power
        P_pa, Pr = ut.elevation_to_pressure_pa(self.vars['site_elevation_ft'])
        T_C_G1 = np.minimum(self.df_tot['T'], self.vars['G1_Tlim_C'])
        T_C_G2 = np.minimum(self.df_tot['T'], self.vars['G2_Tlim_C'])
        rho_G1_array = ut.calc_rho(P_pa=P_pa, T_C=T_C_G1)
        rho_G2_array = ut.calc_rho(P_pa=P_pa, T_C=T_C_G2)
        G1_coeffs = [self.vars[f"G1_pwr_c{str(x)}"] for x in range(1,7)]
        G2_coeffs = [self.vars[f"G2_pwr_c{str(x)}"] for x in range(1,7)]
        self.df_tot['G1_max_kW'] = self.vars['G1_q'] * ut.ngpp_maxpower_multi_quadratic((Pr, rho_G1_array), *G1_coeffs)
        self.df_tot['G2_max_kW'] = self.vars['G2_q'] * ut.ngpp_maxpower_multi_quadratic((Pr, rho_G2_array), *G2_coeffs)
        
        # add ngpp operating efficiency
        if self.vars['G1_q'] == 0:
            self.df_tot['G1_heatrate_mmbtu_mwh'] = 0
        else:
            G1_unit_opload_kw = self.df_tot['G1_max_kW'] * self.vars['G1_opfrac'] / self.vars['G1_q']  
            G1_unit_fuel_MMBTU  = ut.ngpp_fuel_consumption_curve((rho_G1_array, G1_unit_opload_kw), 
                                    self.vars['G1_fc_bfix'],
                                    self.vars['G1_fc_mfix'],
                                    self.vars['G1_fc_bvar'],
                                    self.vars['G1_fc_mvar'])
            self.df_tot['G1_heatrate_mmbtu_mwh'] = G1_unit_fuel_MMBTU / ( G1_unit_opload_kw /1000.0)
        if self.vars['G2_q'] == 0:
            self.df_tot['G2_heatrate_mmbtu_mwh'] = 0
        else:
            G2_unit_opload_kw = self.df_tot['G2_max_kW'] * self.vars['G2_opfrac'] / self.vars['G2_q']  
            G2_unit_fuel_MMBTU  = ut.ngpp_fuel_consumption_curve((rho_G2_array, G2_unit_opload_kw), 
                                    self.vars['G2_fc_bfix'],
                                    self.vars['G2_fc_mfix'],
                                    self.vars['G2_fc_bvar'],
                                    self.vars['G2_fc_mvar'])
            self.df_tot['G2_heatrate_mmbtu_mwh'] = G2_unit_fuel_MMBTU / ( G2_unit_opload_kw /1000.0)


        self.df_tot.to_csv(self.basepath + 'Temp/dftota.csv')

        return None

    def function(self, df_tot_in, svmacro, mode, P=0):
        ### svmacro has bare bones sizing data which is 'upstream' of function

        ## size system
        svall = sizesystem.sizesystem(self.vars, svmacro)
        print('Starting Config: ', sizesystem.nameconfig(product=self.vars['product'], sv=svmacro, vars=self.vars))
    
        # save to temp file
        with open(self.basepath+'/Temp/sizing.txt', 'w') as f:
                for key, value in svall.items():
                    f.write('%s:%s\n' % (key, value))

        ## complete size specific portions of df_tot

        # no need for eleectrolyzer variables if DTC-CPLEX
        if self.vars['product'] not in ['DTC-CPLEX']:
            # Eefft
            if self.vars['include_elect'] == 0:
                df_tot_in['Eefft'] = np.full(self.vars['total_time'], 1.0)
            else:
                df_tot_in['Eefft'] = np.asarray(self.vars['elect_efft0']/df_tot_in['Estate'])
            # EmaxkWt
            if self.vars['include_elect'] == 0:
                df_tot_in['EmaxkWt'] = np.full(self.vars['total_time'], 0.0)
            else:
                df_tot_in['EmaxkWt'] = np.minimum(1000*svall['e_MW'] / df_tot_in['Estate'], 
                                                1000*svall['e_MW'] * self.vars['elect_maxdc']/100)
        # BXmaxt
        if self.vars['include_bess'] == 0:
            df_tot_in['BXmaxt'] = np.full(self.vars['total_time'], 0.0)
        else:
            df_tot_in['BXmaxt'] = np.asarray(df_tot_in['Bstate'] * svall['bess_kWh']) 
        # LdXmaxt
        if self.vars['include_ldes'] == 0:
            df_tot_in['LXmaxt'] = np.full(self.vars['total_time'], 0.0)
        else:
            df_tot_in['LXmaxt'] = np.asarray(df_tot_in['Lstate'] * svall['ldes_kWh']) 
        # Wt
        # Wt from W, including simple GT2 losses. Assume sized for max wind size.
        if svall['wf_MW'] == 0:
            lrWt = 0.0
        else:
            maxWpwrkW = svall['wf_MW'] * 1000.0
            lWmaxkW = ((maxWpwrkW**2)*self.vars['pf_gtOPR']*self.vars['pf_gtPh']*self.vars['GT2L']) / \
                    ((self.vars['pf_gtpf']**2) * (self.vars['pf_gtV']**2) * 3000)
            lrWt = lWmaxkW / maxWpwrkW
        df_tot_in['Wt'] = df_tot_in['W'] * svall['wf_MW'] * 1000.0 * (1-lrWt)
        # St_raw
        # St_Raw from S, including power flow losses
        if self.vars['solar_basis'] == 'AC':
            df_tot_in['St_raw'] = df_tot_in['S'] * df_tot_in['Sstate'] * 1000.0 * svall['sf_MW']
        else:
            kWdc = np.asarray(df_tot_in['S']) * np.asarray(df_tot_in['Sstate']) * svall['sf_MW'] * 1000.0
            SkWact, loss_clip, loss_aux, loss_pmt, loss_mv = SolarDC2AC.calcSac(kWdc=kWdc, 
                                                                            T_C=np.array(df_tot_in['T']), 
                                                                            kWi=svall['sf_MWi']*1000.0, 
                                                                            invpf=self.vars['invpf'], 
                                                                            invperpmt=self.vars['invperpmt'], 
                                                                            invavail=self.vars['invavail'], 
                                                                            sauxloss=self.vars['sauxloss'],
                                                                            pmtsize=self.vars['pmtsize'], 
                                                                            pmt_cl=self.vars['pmt_cl'], 
                                                                            pmt_nll=self.vars['pmt_nll'], 
                                                                            mvll=self.vars['mvll'])
            df_tot_in['St_raw'] = SkWact
        
        # for DTC-CPLEX, ignore SBF and simply eliminate negative solar production
        if self.vars['product'] in ['DTC-CPLEX']:
            df_tot_in['St'] = np.maximum(df_tot_in['St_raw'], 0)
        else:
            # otherwise add SBFt
            df_tot_in['SBFt'] = np.where(np.asarray(df_tot_in['St_raw'])<0,
                                         -np.asarray(df_tot_in['St_raw']),
                                         0)
            df_tot_in['St'] = df_tot_in['SBFt'] + df_tot_in['St_raw']

        # don't need KScurtt for DTC-CPLEX
        # # Kscurtt
        # df_tot_in['KScurtt'] = np.where(np.asarray(df_tot_in['St_raw'])>=0,
        #                                 1.0,
        #                                 0.0)
        
        df_tot_in.to_csv(self.basepath + 'Temp/dftotin.csv')

        # run through pyomo rolling window model
        check = False
        if self.vars['product'] == 'LH2':   
            model = pyomo_LH2.roll_lh2
        elif self.vars['product'] == 'NH3':
            model = pyomo_NH3_v2.roll_nh3
        elif self.vars['product'] == 'CFE':
            model = pyomo_CFE.roll_cfe
        elif self.vars['product'] == 'CFE-CPLEX':
            model = pyomo_CFECPLEXv2.roll_cfe
        elif self.vars['product'] == 'CFE-via-NH3':
            model = pyomo_CFEviaNH3.roll_cfenh3
        elif self.vars['product'] == 'DTC-CPLEX':
            model = pyomo_DTC_CPLEX.roll_cfe
        elif self.vars['product'] == 'DTC-SCED-r1':
            model = pyomo_DTC_SCED_r1.roll_cfe
        else:
            check = True

        if check:
            print('\n\n\n\nSTRAIGHT TO JAIL')
            print('Issue with operating mode /pyomo version inputs.')
            quit()
        else:
            final_results = model(vars=self.vars,
                                  dfopsx=df_tot_in,
                                  svar=svall)
            # for DTC-CPLEX, need to combine columns of df_tot_in and final_results 
            if self.vars['product'] == 'DTC-CPLEX':
                final_results = pd.concat([df_tot_in, final_results], axis=1)
            
            final_results.to_csv(self.basepath + 'Temp/opsresults.csv')

        # run through financial model
        if self.vars['product'] == 'LH2':  
            finpy = fin_LH2
        elif self.vars['product'] == 'NH3':
            finpy = fin_NH3_v2
        elif self.vars['product'] == 'CFE':
            finpy = fin_CFE
        elif self.vars['product']== 'CFE-CPLEX':
            finpy = fin_CFE
        elif self.vars['product'] == 'CFE-via-NH3':
            finpy = fin_CFEviaNH3
        elif self.vars['product'] == 'DTC-CPLEX':
            finpy = fin_GOOG_Q1_26
        else:
            print('ERROR: BAD FIN MODE / PRODUCT COMBO: ', self.vars['fin_mode'])
            quit()

        if finpy == fin_GOOG_Q1_26:
            pfx_int, pfx_ext, lcoe_int, lcoe_ext = finpy.calc_lcoe(vars=self.vars, 
                                                                   svar=svall, 
                                                                   opsx=final_results, 
                                                                   mode=mode,
                                                                   basepath=self.basepath)
            if self.vars['financialmetrics'] == 'Internal':
                pfx = pfx_int
                finmetric = lcoe_int
            else:
                pfx = pfx_ext
                finmetric = lcoe_ext
        else:
            pfxi = finpy.build_pfx(vars=self.vars, 
                            svar=svall, 
                            opsx=final_results, 
                            dftotin= df_tot_in, 
                            basepath=self.basepath,
                            mode= mode)
            pfx, lcox = finpy.calc_lcox(vars=self.vars, pfxi=pfxi)
            finmetric = lcox
        
        # obtain operating metrics
        metrics = {}
        metrics['Renewables_Utilized'] = round(1 - ((final_results['Wcurtt'].sum() + final_results['Scurtt'].sum()) / 
                                              (final_results['St'].sum() + final_results['Wt'].sum())), 4)
        if self.vars['product'] == 'LH2':  
            # LH2 operating metric is fraction of LH2 load coming from NGt
            metrics['Uptime_NGt'] = 1 - final_results['NGt'].sum() / final_results['Lt'].sum()
        elif self.vars['product'] == 'NH3': 
            # PtX uptime
            metrics['Uptime_NH3'] = round(final_results['Kptxt'].sum()/self.vars['dispatch_time'], 4)
            # steam turbine uptime
            metrics['Uptime_ST'] = round(final_results['Kstt'].sum()/self.vars['dispatch_time'], 4)
            # electrolyzer uptime
            metrics['Uptime_Elect'] = round(final_results['KEt'].sum()/self.vars['dispatch_time'], 4) 
            # NGt
            metrics['Uptime_DirectGreen'] = round(1-final_results['NGt'].sum()/(final_results['Eact'].sum() + final_results['Eauxt'].sum() + final_results['Lt'].sum()), 6)  
            # utilization NH3
            metrics['Utilization_NH3'] = round(final_results['PTXt'].sum()/(self.vars['dispatch_time']/8760)/svall['NH3_tpy'], 4)
             # utilization electrolyzer
            metrics['Utilization_E'] = round(final_results['Edct'].sum()/(self.vars['dispatch_time'])/(svall['e_MW']*1000), 4)
            # CFE if Eauxt is included in EAC calc
            ng2Eauxt = np.maximum(0, np.asarray(final_results['NGauxt'] - final_results['Lt']))
            shadowCt = final_results['Ct'].sum() + ng2Eauxt.sum() - min(final_results.at[final_results.index[-1],'BXt'] + 
                                                                    final_results.at[final_results.index[-1],'LdXt'] -
                                                                    final_results.at[0, 'BXt'] - 
                                                                    final_results.at[0, 'LdXt'],
                                                                    0)
            eacloads =  final_results['Eact'].sum() + final_results['ETt'].sum() + final_results['Eauxt'].sum()  
            metrics['Shadow CFE incl Electrolyzer Aux'] = round(1 - shadowCt / eacloads, 6)
            # CFE if all loads are included
            shadowCt = final_results['Ct'].sum() + final_results['NGauxt'].sum() - min(final_results.at[final_results.index[-1],'BXt'] + 
                                                                                    final_results.at[final_results.index[-1],'LdXt'] -
                                                                                    final_results.at[0, 'BXt'] - 
                                                                                    final_results.at[0, 'LdXt'],
                                                                                    0)
            eacloads = final_results['Eact'].sum() + final_results['ETt'].sum() + final_results['Eauxt'].sum() + final_results['Lt'].sum()
            metrics['Shadow CFE incl all aux loads'] = round(1 - shadowCt / eacloads, 6)
        elif self.vars['product'] in ['CFE', 'CFE-CPLEX', 'Mg']:
            # utilization
            metrics['Utilization_Lt'] = round(final_results['Lt'].sum()/(self.vars['dispatch_time'])/(self.vars['Load_max']*1000), 4)
            # fraction load from GTO
            if 'GTOt' in final_results.columns.tolist():
                metrics['FracLoadFrom_GTOt'] = round(final_results['GTOt'].sum()/final_results['Lt'].sum(), 4)
            else:
                metrics['FracLoadFrom_GTOt'] = 0
            # fraction load from Ngt
            metrics['FracLoadFrom_NGt'] = round(final_results['NGt'].sum()/final_results['Lt'].sum(), 4)
        elif self.vars['product'] == 'DTC-CPLEX':
            # utilization
            metrics['Utilization_Lt'] = round(final_results['Lt'].sum()/(self.vars['dispatch_time'])/(self.vars['Load_max']*1000), 4)
            # fraction load from NGt
            metrics['FracLoadFrom_NGt'] = round((final_results['G1t'].sum() + final_results['G2t'].sum())/final_results['Lt'].sum(), 4)
            # fraction load from Zt
            metrics['FracLoadFrom_Zt'] = round(final_results['Zt'].sum()/final_results['Lt'].sum(), 4)
        elif self.vars['product'] == 'CFE-via-NH3': 
            # PtX uptime
            metrics['Uptime_NH3'] = round(final_results['Kptxt'].sum()/self.vars['dispatch_time'], 4)
            # steam turbine uptime
            metrics['Uptime_ST'] = round(final_results['Kstt'].sum()/self.vars['dispatch_time'], 4)
            # electrolyzer uptime
            metrics['Uptime_Elect'] = round(final_results['KEt'].sum()/self.vars['dispatch_time'], 4) 
            # utilization electrolyzer
            metrics['Utilization_E'] = round(final_results['Edct'].sum()/(self.vars['dispatch_time'])/(svall['e_MW']*1000), 4)
            # utilization NH3
            metrics['Utilization_NH3'] = round(final_results['PTXt'].sum()/(self.vars['dispatch_time']/8760)/svall['NH3_tpy'], 4)
            # utilization load
            metrics['Utilization_Lt'] = round(final_results['Lt'].sum()/(self.vars['dispatch_time'])/(self.vars['Load_max']*1000), 4)
            # fraction coming from NGt
            metrics['FracLoad(incl E & aux)FromNH3'] = round(final_results['NGt'].sum()/(final_results['Lt'].sum() + 
                                                                          final_results['Eact'].sum() + 
                                                                          final_results['Eauxt'].sum() + 
                                                                          final_results['Nauxt'].sum()), 4)
            # fraction exported
            metrics['FracGenExported'] = round(final_results['Zt'].sum()/(final_results['St'].sum() + 
                                                                          final_results['Wt'].sum()), 4)
            # fraction NH3 short
            invfinal = final_results.at[self.vars['dispatch_time']-1, 'XNt']
            invinit = final_results.at[0, 'XNt']
            delta = max(0, invinit - invfinal)
            metrics['FracSelfSufficientNH3'] = round(1-(final_results['N2t'].sum() + delta) / final_results['N3t'].sum(), 4)
            # storage duration
            metrics['StorageDuration'] = ut.ammonia_storage_hrs(vars=self.vars, dfops=final_results)


        # obtain cfe metric, which is always sum(Ct) / (sum(load) for relavant loads)
        if self.vars['product'] == 'LH2':  
            loadcols = ['Lt', 'Eact', 'Eauxt']
        elif self.vars['product'] == 'NH3': 
            # NH3 loads include ETt, thermal load to SOEC (which can be supplied via electricity->TES->SOEC)
            loadcols = [ 'Eact', 'ETt']
        elif self.vars['product'] in ['CFE', 'CFE-CPLEX', 'Mg', 'DTC-CPLEX']:
            loadcols = ['Lt']
        elif self.vars['product'] == 'CFE-via-NH3':
            loadcols = ['Lt', 'Eact', 'Eauxt', 'Nauxt']
        grossloads=0
        for col in loadcols:
            grossloads += final_results[col].sum()
        # net carbon includes dESS. All units here are kWh
        netcarbon = final_results['Ct'].sum() - min(final_results.at[final_results.index[-1],'BXt'] + 
                                                    final_results.at[final_results.index[-1],'LdXt'] -
                                                    final_results.at[0, 'BXt'] - 
                                                    final_results.at[0, 'LdXt'],
                                                    0)
        metrics['CFE'] = round(1 - netcarbon / grossloads, 6)

        return final_results, pfx, finmetric, metrics, svall

    def run_single(self, mode, saveflag):
        # build simple sizing case from 'initial' sizes
        sizesimple = {'W': self.vars['W_initial'],
                      'S': self.vars['S_initial'],
                      'ILR': self.vars['ILR_initial'],
                      'E':self.vars['E_initial'],
                      'r':self.vars['r_initial'],
                      'X':self.vars['X_initial'],
                      'B':self.vars['B_initial'],
                      'L':self.vars['L_initial']}
        # get config name
        config = sizesystem.nameconfig(product=self.vars['product'], sv=sizesimple, vars=self.vars)
        
        # build df_tot_in
        if self.vars['product'] in ['DTC-CPLEX']:
            null = self.build_dfops_dtc_cplex(mode=mode)
        else:
            null = self.build_dfops(mode=mode)

        # run using function
        ops, pf, finmetric, metrics, svall = self.function(df_tot_in=self.df_tot,
                                                                     svmacro=sizesimple,
                                                                     mode=mode)
        # print results

        print('Financial Metric: ', round(finmetric,2))
        for key in metrics:
            print(key, ': ', metrics[key])
        print('Detailed Sizing: ', svall)

        if saveflag:
            savefolder = self.basepath + '/Results/' + self.dtstr + '_' + self.scenario
            if os.path.exists(savefolder):
                pass
            else:
                os.makedirs(savefolder)
            # save metadata
            metadata = pd.DataFrame(index=self.df_input.index.tolist())
            metadata['Variable'] = self.df_input['VARIABLE'].values
            metadata[self.scenario] = self.df_input[self.scenario].values
            metadata.to_csv(savefolder + '/' + str(self.dtstr) + '_' + self.scenario + '_runmetadata.csv')
            # save operating data
            ops.to_csv(savefolder + '/' + str(self.dtstr) + '_' + self.scenario + '_ops.csv')
            pf.to_csv(savefolder + '/' + str(self.dtstr) + '_' + self.scenario + '_pf.csv')
            # save detailed sizing
            with open(savefolder+'/'+ str(self.dtstr) + '_' + self.scenario + '_sizing.txt', 'w') as f:
                for key, value in svall.items():
                    f.write('%s:%s\n' % (key, value))

            # excel bridge
            if mode=='Detailed':
                print('Writing Xcel Bridge')
                if self.vars['product']=='CFE-CPLEX' or self.vars['product']=='CFE':
                    xbfunc = xb_CFECPLEX.xcelbridge
                X = xbfunc(d=ops.copy(),
                           dtstr=self.dtstr,
                           svar=svall,
                           vars=self.vars.copy(),
                           years=self.vars['proj_life'],
                           n=self.scenario,
                           basepath=self.basepath)
                xboutpath = savefolder + '/' + str(self.dtstr) + '_' + self.scenario + '_xb.csv'
                X.to_csv(xboutpath)
                print('Xcel Bridge saved to: ', xboutpath)


        print('\n\n')

        return finmetric, metrics, config, svall
    
    def run_optimize(self, saveflag, targetA, targetB):
        # build df_tot_in
        if self.vars['product'] in ['DTC-CPLEX']:
            null = self.build_dfops_dtc_cplex(mode="Simple")
        else:
            null = self.build_dfops(mode="Simple")

        if self.vars['product'] in ['CFE-via-NH3', 'DTC-CPLEX'] or targetA==targetB:
            pass
        else:
            print('\n')
            print('WARNING: Different values entered for OptMetricA & OptMetricB, but product only requires MetricA.')
            print('Rewriting OptMetricB with OptMetricA')
            print('\n')
            targetB=targetA

        if self.vars['product'] in ['CFE', 'Mg', 'CFE-CPLEX']:
            metricA, metricB = 'CFE', 'CFE'
        elif self.vars['product'] in ['DTC-CPLEX']:
            metricA, metricB = 'CFE', 'Utilization_Lt'
        elif self.vars['product'] == 'LH2':
            metricA, metricB = 'Uptime_NGt', 'Uptime_NGt'
        elif self.vars['product'] == 'NH3':
            metricA, metricB = 'Uptime_NH3', 'Uptime_NH3'
        elif self.vars['product'] == 'CFE-via-NH3':
            metricA, metricB = 'Uptime_NH3', 'FracSelfSufficientNH3'

        # run optimizer
        if self.vars['product'] in ['CFE', 'Mg', 'CFE-CPLEX']:
            winningconfig, LCOE_winning, MetricA_winning, MetricB_winning, dff, pff, optimizationhistory, metrics, svall = optimize.optimize_v1_cfe(ptxclass=self,
                                                                                                                    metricA=metricA,
                                                                                                                    metricB=metricB,
                                                                                                                    targetmA=targetA,
                                                                                                                    targetmB=targetB,
                                                                                                                    saveflag=saveflag)
        else:
            winningconfig, LCOE_winning, MetricA_winning, MetricB_winning, dff, pff, optimizationhistory, metrics, svall = optimize.optimize_v1_all(ptxclass=self,
                                                                                                                                metricA=metricA,
                                                                                                                                metricB=metricB,
                                                                                                                                targetmA=targetA,
                                                                                                                                targetmB=targetB,
                                                                                                                                saveflag=saveflag)

        return winningconfig, dff, pff, optimizationhistory, metrics, LCOE_winning, MetricA_winning, MetricB_winning, svall








        

    






        

        

        




                


