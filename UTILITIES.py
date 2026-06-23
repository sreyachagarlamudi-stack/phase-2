"""
Utility Functions
Date/time handling, financial calculations, curve fitting, degradation modeling
"""
import pandas as pd
import numpy as np
import random
import numpy_financial
import math
import datetime
from scipy.optimize import curve_fit
from scipy.integrate import solve_ivp


def save_csv(df, filename):
    check = False
    count = 1
    while check is False and count <3:
        try:
            df.to_csv(filename)
            check = True
        except:
            #prompt user to  close runlog if open
            input(f"File either not found or open. Check {filename} exists and is not open. Press Enter to continue")
            count+=1

    return None



def checkandfixnan(x, default):
    if math.isnan(x):
        return default
    else:
        return x

def get_depreciation_list(depcase):
    MACRS5 = [0.20, 0.32, 0.1920, 0.1152, 0.1152, 0.0576]
    MACRS7 = [0.1429, 0.2449, 0.1749, 0.1249, 0.0893, 0.0892, 0.0893, 0.046]
    MACRS15 = [0.05, 0.0950, 0.0855, 0.0770, 0.0693,
               0.0623, 0.059, 0.059, 0.0591, 0.059,
               0.0591, 0.0590, 0.0591, 0.0590, 0.0591, 0.0295]
    MACRS20 = [0.0375, 0.0722, 0.0668, 0.0618, 0.0571, 
                0.0528, 0.0489, 0.0452, 0.0446, 0.0446,
                0.0446, 0.0446, 0.0446, 0.0446, 0.0446,
                0.0446, 0.0446, 0.0446, 0.0446, 0.0446, 0.0223]
    
    SL10 = 10 * [1/10]
    SL12 = 12 * [1/12]
    SL15  = 15 * [1/15]
    SL20 = 20 * [1/20]
    SL25 = 25 * [1/25]

    if depcase == '5yrMACRS':
        l = MACRS5
    elif depcase == '7yrMACRS':
        l = MACRS7
    elif depcase == '15yrMACRS':
        l = MACRS15
    elif depcase == '20yrMACRS':
        l = MACRS20
    elif depcase == '10yrSL':
        l = SL10
    elif depcase == '12yrSL':
        l = SL12
    elif depcase == '15yrSL':
        l = SL15
    elif depcase == '20yrSL':
        l = SL20
    elif depcase == '25yrSL':
        l = SL25
    else:
        print('BAD DEPCRECIATION SCENARIO. ASSIGNING 0 VALUE TO DEPRECIATION')
        l = [0]

    for z in range(len(l), 40):
        l.append(0.00)
    return l

def dSdt_log(t, y, a, b):
    # State function to define degradation for log/ln curvature
    # a, b are coefficients for degradation of form rate=a*ln(t)+b
    # where rate is %/1000hr
    rate = eq_ln(t, a, b)
    dSdt = -y * (1 / 1000) * rate
    return dSdt

def eq_ln(x,a,b):
    Y = a*np.log(x)+b
    return Y

def dsdt_constant(t, y, c):
    # State function to define constant degradation
    # c is rate of degradation in %/1000hr
    dSdt = -y*(c/1000/100)
    return dSdt

def eq_constantdeg(t, c):
    S = (1-c)**t
    return S

def eq_linear(x,a,b):
    Y = a*x + b
    return Y

def isquadraticthreeinputs(xs):
    if xs[0]==xs[1] or xs[0]==xs[2] or xs[1]==xs[2]:
        check = False
    else:
        check = True
    return check

def quadratic(x, a, b, c):
    return a*(x**2) + b*x + c

def datestringconvert(t):
    tstr = t[0] + t[1] + '-' + t[3] + t[4] + '-' + t[6:]
    return tstr

def datetimestringconvert(t):
    tstr = str(t.month)+ '-' + str(t.day) + '-' + str(t.year)
    return tstr

def get_design_space(inc, minimum, maximum):
    ## generates list of discrete points within design space
    # step 1: convert min and max to integer multipliers of increment
    n_min = math.ceil(minimum/inc)
    n_max = math.ceil(maximum/inc)

    # step 2: create list, and append value for each integer in range
    # if n_min == n_max, range(n_min, n_max) will yield no values, have to treat separately
    # use min() and max() to ensure values go in right order
    designspace = []
    if n_min == n_max:
        designspace.append(n_min*inc)
    else:
        for x in range(min(n_min,n_max), max(n_min,n_max)+1):
            designspace.append(x*inc)
    # step 3: return list
    return designspace

def get_datetimestring():
    dt = datetime.datetime.utcnow()
    stry = str(dt.year)
    strm = str(dt.month)
    if len(strm) == 1:
        strm = '0' + strm
    strd = str(dt.day)
    if len(strd) == 1:
        strd = '0' + strd
    strh = str(dt.hour)
    if len(strh) == 1:
        strh = '0' + strh
    strmin = str(dt.minute)
    if len(strmin) == 1:
        strmin = '0' + strmin
    dtstr = stry + '-' + strm + '-' + strd + '-' + strh + strmin

    return dtstr

def get_midpointoflist(list):
    l = len(list)
    if l==1:
        midpoint= list[0]
    elif l%2==1:
        midpoint=list[int(l/2)]
    else:
        midpoint = list[int(l/2+0.25)]
    return midpoint

def curve_fit_optimize(xs, ys, f):
    if ys[0]==0 and ys[2]==0:
        coeffs = [0,0,0]
    else:
        coeffs, pcov = curve_fit(f, xs, ys)

    return coeffs

def get_cdf_from_lis_lores(xlist):
    xlist.sort()
    cdf = pd.DataFrame(index=np.arange(0, 1, 0.01))
    for z in cdf.index:
        n = int(z * len(xlist))
        cdf.at[z, 'X'] = xlist[n]

    return cdf

def get_cdf_from_list_hires(xlist):
    xlist.sort()
    cdf = pd.DataFrame(index=np.arange(0, 1, 0.0005))
    for z in cdf.index:
        n = int(z * len(xlist))
        cdf.at[z, 'X'] = xlist[n]

    return cdf

def get_dtstr():
    dt = datetime.datetime.now(datetime.UTC)
    stry = str(dt.year)
    strm = str(dt.month)
    if len(strm)==1:
        strm = '0' + strm
    strd = str(dt.day)
    if len(strd)==1:
        strd = '0' + strd
    strh = str(dt.hour)
    if len(strh)==1:
        strh = '0' + strh
    strmin = str(dt.minute)
    if len(strmin)==1:
        strmin = '0' + strmin
    dtstr = stry + '-' + strm + '-' + strd + '-' + strh + strmin
    return dtstr

def get_deg_curve_constant(ratepercentperhour, hrs):
    ts = np.arange(0, hrs+8760)
    r = pd.DataFrame(index=ts)
    r['S'] = (1-ratepercentperhour/100)**ts
    return r


def wrap_shift(df, quarter_start):
            # Define the exact hours for each quarter
            hours_per_quarter = [2160, 2184, 2208, 2208]  # Q1, Q2, Q3, Q4

            if quarter_start == 1:
                shift_hours = 0 
            elif quarter_start == 2:
                shift_hours = hours_per_quarter[0]  
            elif quarter_start == 3:
                shift_hours = hours_per_quarter[0] + hours_per_quarter[1] 
            elif quarter_start == 4:
                shift_hours = hours_per_quarter[0] + hours_per_quarter[1] + hours_per_quarter[2]  

            df_shifted = pd.concat([df.iloc[shift_hours:], df.iloc[:shift_hours]]).reset_index(drop=True)
            
            return df_shifted

def wrap_shift_monthly(df, month_start):
            # Define the exact hours for each month
            starting_hour_by_month = [0, 744, 1416, 2160, 2880, 3624, 4344, 5088, 5832, 6552, 7296, 8016]  # MoY

            shift_hours = starting_hour_by_month[month_start-1]

            df_shifted = pd.concat([df.iloc[shift_hours:], df.iloc[:shift_hours]]).reset_index(drop=True)
            
            return df_shifted

def ammonia_storage_hrs(vars, dfops):
    # calcualte difference between storage high/low (base size of storage)
    storage_base = dfops['XNt'].max() - dfops['XNt'].min()
    # # calculate storage delta (change), and accumulation/depletion, if any
    # storage_delta = dfops.at[dfops.index.tolist()[-1], 'XNt'] - dfops.at[0, 'XNt']
    # storage_accumulation = max(0, storage_delta)
    # storage_depletion = - min(0, storage_delta)
    # calculate storage required
    #storage_mt = storage_base + storage_depletion - storage_accumulation
    storage_mt = storage_base
    # convert from mt NH3 to duration
    storage_mmbtu = storage_mt * 1000.0 * 18.6 / 1055.0
    storage_mwh = storage_mmbtu / vars['NG_Hrate']
    storage_hrs = storage_mwh / vars['Load_max']

    return storage_hrs


def elevation_to_pressure_pa(elevation_ft: float) -> float:
    """ISA standard atmosphere. Returns pressure in Pa."""
    h_m = elevation_ft * 0.3048
    P_Pa = 101325.0 * (1.0 - 2.25577e-5 * h_m) ** 5.25588
    Pr = P_Pa / 101325.0
    return P_Pa, Pr

def calc_rho(P_pa, T_C):
    T_K = T_C + 273.15
    rho = P_pa / (8.31446261815324 * T_K)
    return rho

def ngpp_maxpower_multi_quadratic(X, c1, c2, c3, c4, c5, c6):
    # X is (Pr, rho)
    # c1-6 are coefficients to define maxpower as quadratic f(rho, Pr)
    Pr, rho = X
    a1 = c1 + c2 * Pr
    a2 = c3 + c4 * Pr
    a3 = c5 + c6 * Pr

    maxpower = a1 * (rho**2) + a2 * rho + a3

    return maxpower

def ngpp_fuel_consumption_curve(X, b_fixed, m_fixed, b_variable, m_variable):
    # Returns generator consumption in MMBTU/hr
    # X is tuple of (density in mol/m3, power in kW)
    
    # overall equation is Fuel = Fixed [mmbtu/hr] + Variable_Coeff [mmbtu/hr/kW] * Load [kW]
    # Fixed is linear function of density: Fixed = b_fixed + m_fixed * density
    # Variable is linear function of density: Variable = b_variable + m_variable * density
    # Fuel = b_fixed + m_fixed * density + (b_variable + m_variable * density) * Load [kW]
    density, power = X
    fixed = b_fixed + m_fixed * density
    variable = b_variable + m_variable * density
    fuel = fixed + variable * power
    
    return fuel