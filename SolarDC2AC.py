"""
Solar DC/AC Conversion
Inverter efficiency modeling with temperature dependence
"""
import numpy as np
import pandas as pd

def calcSac(kWdc, T_C, kWi, invpf=0.92, invperpmt=6, invavail=99, sauxloss=2,
               pmtsize=5040, pmt_cl=0.85, pmt_nll=0.15, mvll=1, invsize=840.0):

    '''
    INPUTS
    # kWdc is a numpy array in kW (timeseries). Before this calculation, production timeseries (kW/kW) must be multiplied by [kWdc installed] and [degradation state] 
    # T_C is numpy array in degC (timeseries)
    # kWi is float or int, total nameplate size of all inverters
    # invpf is a fraction (power factor)
    # invperpmt is int (number of inverters per PMT/MVT, design characteristic)
    # invavail is a percentage (inverter availability as simplistic means of overall plant availavility)
    # sauxloss is in W/kW (solar auxiliary loss)
    # pmtsize in kW (size of PMT/MVT)
    # pmt_cl in % (copper loss, % at full utilization)
    # pmt_nll in % (no load loss, fixed % of nameplate size)
    # mvll in % (medium voltage wiring losses, % at full utilization at nameplate size of PMT/MVTs)
    # invsize in kW (size of one inverter at PF=1.0)

    OUTPUTS
    # kWac1D is a numpy array in kW, meausured at PV substation (inlet side of GSU)
    # loss_clip is a numpy array in kW, inverter clipping loss
    # loss_aux is a numpy array in kW, solar aux loss
    # loss_pmt is a numpy array in kW, pmt (MVT) losses. includes no load (fixed) and copper (variable) losses.
    # loss_mv is a numpy array in kW, MV wiring loss

    '''

    # size solar system
    qinv = np.ceil(kWi / invsize)
    qpmt = np.ceil(qinv / invperpmt)
    # calculate single inverter limit
    liminvsingle = single_inverter_lim(T_C)
    # calculate net inverter limit
    liminvnet = liminvsingle * qinv * invpf
    #calculate ac-at-inverter and inverter clipping losses
    kWac1A = np.minimum(liminvnet, kWdc) * invavail / 100.0
    loss_clip = np.maximum(0, kWdc - kWac1A)
    # calculate solar aux loss
    loss_aux = np.maximum(0, kWac1A) * sauxloss / 1000.0
    # calculate kW-to-PMT
    kWac1B = kWac1A - loss_aux
    # calculate pmt losses
    loss_pmtcl = ((kWac1B / qpmt / pmtsize)**2) * pmtsize * qpmt * pmt_cl / 100.0
    loss_pmtnll = np.full(kWdc.shape[0], pmt_nll * pmtsize * qpmt / 100.0)
    loss_pmt = loss_pmtnll + loss_pmtcl
    # calculate kW-downstream-PMT
    kWac1C = kWac1B - loss_pmt
    # calculate MV wiring loss. note that flow here can be bidirectional due to pmt no load loss
    loss_mv = ((kWac1C / qpmt / pmtsize)**2) * kWac1C * mvll / 100.0
    # calcualate power at PV sub
    kWac1D = kWac1C - loss_mv

    return kWac1D, loss_clip, loss_aux, loss_pmt, loss_mv

def single_inverter_lim(tempray, invsize=840):
    # tempray is a numpy array in degC
    # this is currently hard-coded for a specific TMEIC model, but should be generalized.
    invlimsingle = np.full(tempray.shape[0], invsize)
    invlimsingle = np.where(tempray>=25,
                            ((765-840)/25)*tempray+915,
                            invlimsingle
                            )
    invlimsingle = np.where(tempray>=50,
                            ((0-765)/3)*tempray+13515,
                            invlimsingle
                            )
    invlimsingle = np.where(tempray>=53,
                            0,
                            invlimsingle)
    return invlimsingle
