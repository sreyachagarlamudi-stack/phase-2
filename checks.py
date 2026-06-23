"""
Configuration Validation
Input parameter checks and consistency validation
"""

def checks(vars, mode):
    
    check = True
    
    if vars['include_elect'] == 0 and vars['Load_min'] > vars['Load_max']:
        print('\n\n\n\nCONFIGURATION ERROR')
        print('Load_max less than Load_min.')
        check = False
    if vars['product']=='LH2' and (vars['window_size']-vars['step_size']) < 1:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("In Dispatch section, 'window_size' needs to be larger than 'step_size'")
        check = False
    if vars['life_B']<vars['proj_life'] and vars['structure_b']=='Integrated' and vars['include_bess']==1:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("Bess life is shorter than project life")
        print('BESS Life: ', vars['life_B'], '\tProj Life: ', vars['proj_life'])
        check = False
    if vars['life_Ld']<vars['proj_life'] and vars['structure_l']=='Integrated' and vars['include_ldes']==1:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("ldes life is shorter than project life")
        check = False
    if vars['G1_life']<vars['proj_life'] and vars['structure_ng']=='Integrated' and vars['include_capacity']==1 and vars['G1_units']>0:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("ng life is shorter than project life")
        check = False
    if vars['G2_life']<vars['proj_life'] and vars['structure_ng']=='Integrated' and vars['include_capacity']==1 and vars['G2_units']>0:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("ng life is shorter than project life")
        check = False
    if vars['td_basis']=='PSS' and vars['window_size']>48:
        print('\n\n\n\nCONFIGURATION ERROR')
        print("Cannot use Pseudo-Steady-State turndown method with window_size > 48hrs")
        check = False
    if vars['product'] == 'CFE-via-NH3':
        print('\nSENSE CHECK.')
        print('YOU ARE RUNNING CFE-via-NH3. ARE YOU ABSOLUTELY SURE THAT "NG" INPUT IS CORRECT FOR NH3 COMBUSTION?')
        print('NG INPUT: ', vars['ng_spec'])
        print('The implied makeup NH3 price of "NG_Pfeed" is: ', round(vars['NG_Pfeed']*17.82,2), '$/MT')
        print('ARE YOU ABSOLUTELY SURE THAT IS CORRECT?')
        print('\n')
    if (vars['product']=='CFE' or vars['product']=='Mg') and vars['operating_mode']=='grid interaction' and vars['include_capacity']==0 and vars['Load_min']!=0:
        if vars['max_grid_import']== 'No Import' or (vars['max_grid_import']=='Fixed' and vars['fixed_import']<vars['Load_min']):
            print('\n\n\n\nCONFIGURATION ERROR')
            print("System is set to Grid Interaction with no capacity, but Max Grid Import is either set to No Import or set < Load_min")
            print('Add some means of providing capacity!!')
            check = False
    if vars['product'] in('LH2') and vars['ng_spec'] != 'ShadowPenalty':
        print('\n\n\n\nCONFIGURATION ERROR')
        print(vars['product'], " is intended to work with 'ShadowPenalty' capacity option!")
        check = False
    if vars['product'] in('NH3') and vars['ng_spec'] not in ('ShadowPenalty', 'FixedAuxRate'):
        print('\n\n\n\nCONFIGURATION ERROR')
        print(vars['product'], " is intended to work with 'ShadowPenalty' or 'FixedAuxRate' capacity option!")
        check = False
    if  vars['product'] in('NH3') and vars['ng_spec'] == 'ShadowPenalty' and vars['NG_Pbasis']=='Fixed' and vars['NG_Pfeed'] * vars['NG_Hrate'] >= 80:
        print('WARNING: ShadowPenalty is priced at ', vars['NG_Pfeed'] * vars['NG_Hrate'], ' $/MWh, this may make system choose to power aux loads with renewables instead of make H2.')
    if vars['product'] in ('NH3', 'LH2', 'CFE-via-NH3') and vars['NONCFE_pen']<250:
        print('WARNING: System has electrolyzer & NONCFE_pen is <250. This may break implicit assumption that H2 earns PTC!')
        print('\n')

    return check