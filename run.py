"""
Main Execution Script
Runs PtXv3 optimization framework in Simple, Detailed, or Opt modes
"""
from ptxclass_r0 import ptx
import numpy as np
import UTILITIES as ut
import pandas as pd
import os
from pathlib import Path


# Operating mode selection (exactly one must equal 1)
simple = 0
detailed = 0
opt = 1

# Input configuration sheet
inputsheet = 'PtXv3_config'

# Scenarios to run
scenarios = ['BASE_SCENARIO']
# Example multi-scenario runs:
# scenarios = ['SCENARIO_A', 'SCENARIO_B', 'SCENARIO_C']

# Uptime metric(s) imposed as binary constraints in the optimization.
# CFE: Only metric used is CFE (you can ignore MetricB)
# LH2: Only metric used is [fraction power not supplied by NGt] (you can ignore MetricB)
# NH3: Only metric used in uptime_NH3 (you can ignore MetricB)
# CFE-via-NH3: MetricA is uptime_NH3. MetricB is [Fraction NH3 burned that is self supplied]. Setting either to 0 to ignore.f

#OptMetricAs = [0.5, 0.6, 0.7]
#OptMetricAs = [0.75, 0.80]
#OptMetricAs = [0.85, 0.9, 0.95, 0.98]
OptMetricAs = [0.98]
OptMetricBs = [0.995]

# Saveflag #
saveflag = 1

###################################################################################

# Get basepath
cwd = os.getcwd()
base_path = Path(cwd).as_posix() + '/'

# get mode


if (simple + detailed + opt) != 1:
    print('ERROR: Exactly one operating mode must be selected')
    quit() 
else:
    if simple==1:
        mode = 'Simple'
    elif detailed==1:
        mode = 'Detailed'
    else:
        mode = 'opt'

# load input sheet
df_input = pd.read_excel(base_path + '/Scenarios/' + inputsheet + '.xlsx', sheet_name='Main')

# Get dtstr
dtstr = ut.get_dtstr()

# open runlog
runlogpath = base_path + '/Results/runlog.csv'
runlog = pd.read_csv(runlogpath, index_col=0)
initiallogcount = len(runlog.index) + 1

## SINGLE MODE
if mode=='Simple' or mode=='Detailed':
    # get tdstr
    dtstr = ut.get_dtstr()
    # cycle through scenarios
    for scen in scenarios:
        print('Starting: ', scen)
        print('DateTimeString: ', dtstr)
        print('Running Mode: ', mode)
        logcount = len(runlog.index) + 1
        # create class
        X = ptx(df_input=df_input, basepath=base_path, scenario=scen, dtstr=dtstr, mode=mode)
        # run model
        finmetric, metrics, config = X.run_single(mode=mode, saveflag=saveflag)
        runlog.at[logcount, 'dtstr'] = dtstr
        runlog.at[logcount, 'runmode'] = mode
        runlog.at[logcount, 'scenario'] = scen
        runlog.at[logcount, 'config'] = config
        runlog.at[logcount, 'FinMetric'] = finmetric
        for key, value in metrics.items():
            runlog.at[logcount, key] = value
        
        # save runlog just in case next run crashes
        ut.save_csv(runlog, runlogpath)
    print('Results below, also available in Results folder')
    print(runlog.loc[initiallogcount:logcount])
    ut.save_csv(runlog, runlogpath)

## OPT MODE
elif mode == 'opt':
    for scen in scenarios:
        for tA in OptMetricAs:
            for tB in OptMetricBs:
                # get tdstr
                dtstr = ut.get_dtstr()
                # status update
                print('STARTING NEW OPTIMIZATION')
                print('Scenario: ', scen)
                print('MetricA: ', tA)
                print('MetricB: ', tB)
                print('DateTimeString: ', dtstr)
                logcount = len(runlog.index) + 1
                # create class
                X = ptx(df_input=df_input, basepath=base_path, scenario=scen, dtstr=dtstr, mode=mode)
                # run optimization
                winningconfig, dff, pff, optimizationhistory, metrics, LCOE_winning, MetricA_winning, MetricB_winning = X.run_optimize(saveflag=saveflag,
                                                            targetA=tA,
                                                            targetB=tB)
                # update logfile
                runlog.at[logcount, 'dtstr'] = dtstr
                runlog.at[logcount, 'scenario'] = scen
                runlog.at[logcount, 'runmode'] = mode
                runlog.at[logcount, 'FinMetric'] = LCOE_winning
                runlog.at[logcount, 'config'] = winningconfig
                runlog.at[logcount, 'targetA'] = tA
                runlog.at[logcount, 'targetB'] = tB
                runlog.at[logcount, 'MetricA'] = MetricA_winning
                runlog.at[logcount, 'MetricB'] = MetricB_winning
                for key, value in metrics.items():
                    runlog.at[logcount, key] = value
                
                # set up results folder
                savefolder = base_path + '/Results/' + dtstr + '_' + scen
                if os.path.exists(savefolder):
                    pass
                else:
                    os.makedirs(savefolder)
                # save metadata and optimization history no matter what
                metadata = pd.DataFrame(index=df_input.index.tolist())
                metadata['Variable'] = df_input['VARIABLE'].values
                metadata[scen] = df_input[scen].values
                metadata.to_csv(savefolder + '/' + str(dtstr) + '_' + scen + '_runmetadata.csv')
                optimizationhistory.to_csv(savefolder + '/' + str(dtstr) + '_' + scen + '_opthistory.csv')
                # save df and pf only if desired
                if saveflag:
                    dff.to_csv(savefolder + '/' + str(dtstr) + '_' + scen + '_optimalops.csv')
                    pff.to_csv(savefolder + '/' + str(dtstr) + '_' + scen + '_optimalpf.csv')
    
                # save runlog just in case next run crashes
                ut.save_csv(runlog, runlogpath)
    
    print('Results below, also available in Results folder')
    print(runlog.loc[initiallogcount:logcount])      
    ut.save_csv(runlog, runlogpath)