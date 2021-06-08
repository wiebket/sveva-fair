#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on 18-05-2021
@author: wiebket
"""

import pandas as pd
import numpy as np
import scipy as sp
import sklearn.metrics as sklearn_metrics


def _compute_min_cdet(fnrs, fprs, thresholds, dcf_p_target, dcf_c_fn, dcf_c_fp):
    """
    Compute the minimum of the detection cost function as defined in the 
    NIST Speaker Recognition Evaluation Plan 2019.
    """

    cdet = np.array([fnr*dcf_c_fn*dcf_p_target for fnr in fnrs]) + np.array([fpr*dcf_c_fp*(1-dcf_p_target) for fpr in fprs])
    min_ix = np.nanargmin(cdet)
    min_cdet = cdet[min_ix]
    min_cdet_threshold = thresholds[min_ix]

    return(min_cdet, min_cdet_threshold)



def _evaluate_sv(sc, lab, dcf_p_target, dcf_c_fn, dcf_c_fp):
    """
    Calculate:
    1. false negative (false reject) and false positive (false accept) rates
    2. minimum of the detection cost function and corresponding threshold score value
    3. equal error rate and corresponding threshold score value
    """

    # Calculate false negative (false reject) and false positive (false accept) rates
    fprs, fnrs, thresholds = sklearn_metrics.det_curve(lab, sc, pos_label=1)

    # Calculate the minimum of the detection cost function and corresponding threshold
    min_cdet, min_cdet_threshold = _compute_min_cdet(fnrs, 
                                                  fprs, 
                                                  thresholds, 
                                                  dcf_p_target, 
                                                  dcf_c_fn, 
                                                  dcf_c_fp)

    # Calculate the equal error rate and its threshold
    min_ix = np.nanargmin(np.absolute((fnrs - fprs)))
    eer  = max(fprs[min_ix], fnrs[min_ix])*100
    eer_threshold = thresholds[min_ix] 

    return(fnrs, fprs, thresholds, min_cdet, min_cdet_threshold, eer, eer_threshold)



def _subgroup(df, filter_dict:dict):
    """
    Filter dataframe by a demographic subgroup.
    
    ARGUMENTS
    ---------
    df [dataframe]: 
    group_filter [dict]:
    
    OUTPUT
    ------
    """

    filters = ' & '.join([f"{k}=='{v}'" for k, v in filter_dict.items()])
    sg = df.query(filters)

    return(sg[['sc','lab']+list(filter_dict.keys())])



def fpfnth_metrics(df, dcf_p_target=0.05, dcf_c_fn=1, dcf_c_fp=1):
    """
    Calculate 
    
    ARGUMENTS
    ---------
    df [dataframe]: results dataframe with columns ['sc'] (scores), ['lab'] (labels)
    dcf_p_target [float]: detection cost function target (default = 0.05)
    dcf_c_fn [float]: detection cost function false negative weight (default = 1)
    dcf_c_fp [float]: detection cost function  false positive weight (default = 1)
    
    OUTPUT
    ------
    fpfnth [dataframe]:
    metrics [dictionary]:
    """

    if len(df)>0:
        df_eval = _evaluate_sv(df['sc'], df['lab'], dcf_p_target, dcf_c_fn, dcf_c_fp)
        df_fpfnth = pd.DataFrame(data={'fnrs':df_eval[0],
                                       'fprs':df_eval[1],
                                       'thresholds':df_eval[2]})
        
        df_metrics = {'min_cdet':df_eval[3],'min_cdet_threshold':df_eval[4],'eer':df_eval[5],'eer_threshold':df_eval[6]}       

        return(df_fpfnth, df_metrics)

    else:
        return(None)  #TO DO: silent pass --> consider response
    
    
    
def sg_fpfnth_metrics(df, filter_keys:list, dcf_p_target=0.05, dcf_c_fn=1, dcf_c_fp=1):
    """
    This function returns false negative rates, false positive rates and the 
    corresponding threshold values for scores in dataset df. 
    
    ARGUMENTS
    ---------
    df [dataframe]:
        df['sc']: scores
        df['lab']: binary labels (0=False, 1=True)
    filter_keys [list]:
    dcf_p_target [float]: detection cost function target (default = 0.05)
    dcf_c_fn [float]: detection cost function false negative weight (default = 1)
    dcf_c_fp [float]: detection cost function  false positive weight (default = 1)
    
    OUTPUT
    ------
    fpfnth [dataframe]:
    metrics [dictionary]:
    """

    filter_dict = {}
    
    for f_key in filter_keys:
        f_vals = list(df[f_key].unique())
        f_vals.sort()
        filter_dict[f_key] = f_vals

    filter_items = []

    for val0 in filter_dict[filter_keys[0]]:
        try:
            for val1 in filter_dict[filter_keys[1]]:
                try:
                    for val2 in filter_dict[filter_keys[2]]:
                        f_item = {filter_keys[0]:val0, filter_keys[1]:val1, filter_keys[2]:val2}
                        filter_items.append(f_item)
                except IndexError:
                    f_item = {filter_keys[0]:val0, filter_keys[1]:val1}
                    filter_items.append(f_item)
        except IndexError:
            f_item = {filter_keys[0]:val0}
            filter_items.append(f_item)

    fpfnth_list = []
    metrics = {}

    for fi in filter_items:
        try:
            sg = _subgroup(df, fi)
            sg_fpfnth, sg_metrics = fpfnth_metrics(sg, dcf_p_target, dcf_c_fn, dcf_c_fp)
            for key, val in fi.items():
                sg_fpfnth[key] = val
            fpfnth_list.append(sg_fpfnth)
            sg_name = '_'.join([v.replace(" ", "").lower() for v in fi.values()])
            metrics[sg_name] = sg_metrics
        except:
            print('Failed to filter by: ', fi.values())
            pass

    fpfnth = pd.concat(fpfnth_list)

    return(fpfnth, metrics)



def fpfn_min_threshold(df, threshold, ppf_norm=False):
    """
    Calculate the false positive rate (FPR) and false negative rate (FNR) at the minimum threshold value.
    
    ARGUMENTS
    ---------
    df [dataframe]: dataframe, must contain false negative rates ['fnrs'], false positive rates ['fprs'] and threshold values ['thresholds']
    threshold [float]: score at threshold 'min_cdet_threshold' or 'eer_threshold'
    ppf_norm [bool]: normalise the FNR and FPR values to the percent point function (default = False)
    
    OUTPUT
    ------
    list: [FPR, FNR] at minimum threshold value
    """

    # Find the index in df that is closest to the SUBGROUP minimum threshold value
    sg_threshold_diff = np.array([abs(i - threshold) for i in df['thresholds']])
    
    if ppf_norm == True:
        min_threshold_fpr = sp.stats.norm.ppf(df['fprs'])[np.ndarray.argmin(sg_threshold_diff)]
        min_threshold_fnr = sp.stats.norm.ppf(df['fnrs'])[np.ndarray.argmin(sg_threshold_diff)]
    else:
        min_threshold_fpr = df['fprs'].iloc[np.ndarray.argmin(sg_threshold_diff)]  
        min_threshold_fnr = df['fnrs'].iloc[np.ndarray.argmin(sg_threshold_diff)]      

    norm_threshold = [min_threshold_fpr, min_threshold_fnr]

    return norm_threshold



def cdet_diff(fpfnth, metrics, metrics_baseline, dcf_p_target=0.05, dcf_c_fn=1, dcf_c_fp=1):
    
    fpfn_list = []
    for k in metrics.keys():

        # Calculate cdet of subgroup at the overall minimum threshold value
        sg = k.split('_')
        sg_fpfnth = fpfnth[(fpfnth['ref_nationality'].apply(lambda x: x.replace(" ", "").lower())==sg[0]) & 
                              (fpfnth['ref_gender']==sg[1])]
        fpfn_overall_min_cdet = fpfn_min_threshold(sg_fpfnth, metrics_baseline['min_cdet_threshold'])
        sg_cdet_overall_min = fpfn_overall_min_cdet[0]*dcf_c_fp*(1-dcf_p_target) + fpfn_overall_min_cdet[1]*dcf_c_fn*dcf_p_target        
 
        fpfn_list.append([k, sg_cdet_overall_min, metrics[k]['min_cdet']])

    fpfn_df = pd.DataFrame(fpfn_list, columns=['subgroup','sg_cdet_overall_min','sg_min_cdet'])
    
    # Calculate cdet ratios for subgroups
    fpfn_df['overall_cdet_diff'] = fpfn_df['sg_cdet_overall_min']/metrics_baseline['min_cdet']
    fpfn_df['sg_cdet_diff'] = fpfn_df['sg_min_cdet']/fpfn_df['sg_cdet_overall_min']    
    
    return fpfn_df



def fpfn_diff(fpfnth, metrics, metrics_baseline, threshold_type):
    
    fpfn_list = []
    for k in metrics.keys():
        
        # Calculate FPR/FNR at the overall minimum threshold value
        overall_min_cdet = fpfn_min_threshold(fpfnth, metrics_baseline[threshold_type])

        # Calculate FPR/FNR of subgroup at the overall minimum threshold value
        sg = k.split('_')
        sg_fpfnth = fpfnth[(fpfnth['ref_nationality'].apply(lambda x: x.replace(" ", "").lower())==sg[0]) & 
                              (fpfnth['ref_gender']==sg[1])]
        sg_overall_min_cdet = fpfn_min_threshold(sg_fpfnth, metrics_baseline[threshold_type])
        
        # Calculate FPR/FNR of subgroup at the subgroup minimum threshold value
        sg_min_cdet = fpfn_min_threshold(sg_fpfnth, metrics[k][threshold_type])

        fpfn_list.append([k, sg_overall_min_cdet[0], sg_overall_min_cdet[1], sg_min_cdet[0], sg_min_cdet[1]])

    fpfn_df = pd.DataFrame(fpfn_list, columns=['subgroup','overall_fpr','overall_fnr','sg_fpr','sg_fnr'])
    
    fpfn_df['overall_fpr_diff'] = fpfn_df['overall_fpr']/overall_min_cdet[0]
    fpfn_df['overall_fnr_diff'] = fpfn_df['overall_fnr']/overall_min_cdet[1]
    fpfn_df['sg_fpr_diff'] = fpfn_df['sg_fpr']/fpfn_df['overall_fpr']
    fpfn_df['sg_fnr_diff'] = fpfn_df['sg_fnr']/fpfn_df['overall_fnr']
    
    return fpfn_df



def compare_experiments(experiment_dict:dict, comparison:str):
    """
    
    ARGUMENTS
    ---------
    experiment_dict [dict]: key:[fpfnth dataframe, metrics dict]
    comparison [str]:
    
    OUTPUT
    ------
    """
    
    compare_df = []
    compare_metrics = {}
    
    for k, v in experiment_dict.items():
        df = v[0]
        df[comparison] = k
        compare_metrics[k] = v[1]
        compare_df.append(df)
    
    compare_fpfnth = pd.concat(compare_df)
    
    return compare_fpfnth, compare_metrics