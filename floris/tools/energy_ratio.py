# Copyright 2019 NREL

# Licensed under the Apache License, Version 2.0 (the "License"); you may not use
# this file except in compliance with the License. You may obtain a copy of the
# License at http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

import numpy as np
import matplotlib.pyplot as plt
import pandas as pd


def _convert_to_numpy_array(series):
    if hasattr(series, 'values'):
        return series.values
    elif isinstance(series, np.ndarray):
        return series

# def _ratio_of_mean(x, y):
#     """
#     Arguments
#         x: numerator
#         y: denominator
#     """
#     return np.mean(x) / np.mean(y)


def _calculate_bootstrap_iterations(n):
    maximum = 10000
    minimum = 2000
    return int(np.round(max(min(n * np.log10(n), maximum), minimum)))


def _calculate_lower_and_upper_bound(bootstrap_array, percentiles, central_estimate=None, method='simple_percentile'):
    if method is 'simple_percentile':
        lower, upper = np.percentile(bootstrap_array, percentiles)
    else:
        lower, upper = (2 * central_estimate -
                        np.percentile(bootstrap_array, percentiles))
    return lower, upper


def _get_confidence_bounds(confidence):
    return [50 + 0.5 * confidence, 50 - 0.5 * confidence]


def energy_ratio(ref_pow_base, test_pow_base, ws_base,
                 ref_pow_con, test_pow_con, ws_con):
    """
    Compute the balanced energy ratio

    This function is typically called to compute a single balanced 
    energy ratio calculation for a particular wind direction bin.  Note 
    the reference turbine should not be the turbine implementing 
    control, but should be an unaffected nearby turbine, or a synthetic 
    power estimate from a measurement.

    Args:
        ref_pow_base (np.array): Array of baseline reference turbine 
            power.
        test_pow_base (np.array): Array of baseline test turbine power.
        ws_base (np.array): Array of wind speeds for basline.
        ref_pow_con (np.array): Array of controlled reference turbine 
            power.
        test_pow_con (np.array): Array of controlled test turbine power.
        ws_con (np.array): Array of wind speeds in control.

    Returns:
        tuple: tuple containing:

            -   **ratio_base** (*float*): Baseline energy ratio.
            -   **ratio_con** (*float*): Controlled enery ratio.
            -   **ratio_diff** (*float*): Difference in energy ratios.
            -   **p_change** (*float*): Percent change in energy ratios.
            -   **counts_base** (*float*): Number of points in baseline.
            -   **counts_con** (*float*): Number of points in 
                controlled.
            -   **counts_diff** (*float*): Number of points in diff (min
                (baseline,controlled)).
            -   **counts_pchange** (*float*): Number of points in 
                pchange (min(baseline,controlled)).
    """

    # First derive the weighting functions by wind speed
    ws_unique_base = np.unique(ws_base)
    ws_unique_con = np.unique(ws_con)
    ws_unique = np.intersect1d(ws_unique_base, ws_unique_con)

    if len(ws_unique) == 0:
        return np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan, np.nan

    # Mask down to the items in both sides
    base_mask = np.isin(ws_base, ws_unique)
    con_mask = np.isin(ws_con, ws_unique)
    ref_pow_base = ref_pow_base[base_mask]
    test_pow_base = test_pow_base[base_mask]
    ws_base = ws_base[base_mask]
    ref_pow_con = ref_pow_con[con_mask]
    test_pow_con = test_pow_con[con_mask]
    ws_con = ws_con[con_mask]

    ws_unique_base, counts_base = np.unique(ws_base, return_counts=True)
    ws_unique_con, counts_con = np.unique(ws_con, return_counts=True)
    total_counts = counts_base + counts_con

    # Make the weights per wind speed
    weights_base = counts_con.astype(float) / total_counts.astype(float)
    weights_con = counts_base.astype(float) / total_counts.astype(float)

    # Make a weighting array
    lut_base = np.zeros(np.max(ws_unique)+1)
    lut_base[ws_unique] = weights_base
    weight_array_base = lut_base[ws_base]
    lut_con = np.zeros(np.max(ws_unique)+1)
    lut_con[ws_unique] = weights_con
    weight_array_con = lut_con[ws_con]

    # Weighted sums
    weight_sum_ref_base = np.sum(ref_pow_base * weight_array_base)
    weight_sum_test_base = np.sum(test_pow_base * weight_array_base)
    weight_sum_ref_con = np.sum(ref_pow_con * weight_array_con)
    weight_sum_test_con = np.sum(test_pow_con * weight_array_con)

    # Ratio and diff
    ratio_base = weight_sum_test_base / weight_sum_ref_base
    ratio_con = weight_sum_test_con / weight_sum_ref_con
    ratio_diff = ratio_con - ratio_base
    p_change = 100. * ratio_diff / ratio_base

    # Get the counts
    counts_base = len(ref_pow_base)
    counts_con = len(ref_pow_con)
    counts_diff = np.min([counts_base, counts_con])
    counts_pchange = counts_diff

    return ratio_base, ratio_con, ratio_diff, p_change, counts_base, counts_con, counts_diff, counts_pchange


def calculate_balanced_energy_ratio(reference_power_baseline,
                                    test_power_baseline,
                                    wind_speed_array_baseline,
                                    wind_direction_array_baseline,
                                    reference_power_controlled,
                                    test_power_controlled,
                                    wind_speed_array_controlled,
                                    wind_direction_array_controlled,
                                    wind_direction_bins,
                                    confidence=95,
                                    n_boostrap=None,
                                    wind_direction_bin_p_overlap=None,
                                    ):
    """
    Calculate a balanced energy ratio for each wind direction bin.

    Calculate a balanced energy ratio for each wind direction bin.  A 
    reference and test turbine are provided for the ratio, as well as 
    wind speed and wind directions. These data are further divided into 
    baseline and controlled conditions.  The balanced energy ratio 
    function is called and used to ensure a similar distribution of 
    wind speeds is used in the computation, per wind direction bin, for 
    baseline and controlled results.  Resulting arrays, including upper 
    and lower uncertaintity bounds computed through bootstrapping, are 
    returned.  Note the reference turbine should not be the turbine 
    implementing control, but should be an unaffected nearby turbine, 
    or a synthetic power estimate from a measurement

    Args:
        reference_power_baseline (np.array): Array of power of 
            reference turbine in baseline conditions.
        test_power_baseline (np.array): Array of power of test turbine 
            in baseline conditions.
        wind_speed_array_baseline (np.array): Array of wind speeds in 
            baseline conditions.
        wind_direction_array_baseline (np.array): Array of wind 
            directions in baseline case.
        reference_power_controlled (np.array): Array of power of 
            reference turbine in controlled conditions.
        test_power_controlled (np.array): Array of power of test 
            turbine in controlled conditions.
        wind_speed_array_controlled (np.array): Array of wind speeds in 
            controlled conditions.
        wind_direction_array_controlled (np.array): Array of wind 
            directions in controlled case.
        wind_direction_bins (np.array): Wind directions bins.
        confidence (int, optional): Confidence level to use.  Defaults 
            to 95.
        n_boostrap (int, optional): Number of bootstaps, if none, 
            _calculate_bootstrap_iterations is called.  Defaults to 
            None.
        wind_direction_bin_p_overlap (np.array, optional): Percentage 
            overlap between wind direction bin. Defaults to None.

    Returns:
        tuple: tuple containing:

            **ratio_array_base** (*np.array*): Baseline energy ratio at each wind direction bin.
            **lower_ratio_array_base** (*np.array*): Lower confidence bound of baseline energy ratio at each wind direction bin.
            **upper_ratio_array_base** (*np.array*): Upper confidence bound of baseline energy ratio at each wind direction bin.
            **counts_ratio_array_base** (*np.array*): Counts per wind direction bin in baseline.
            **ratio_array_con** (*np.array*): Controlled energy ratio at each wind direction bin.
            **lower_ratio_array_con** (*np.array*): Lower confidence bound of controlled energy ratio at each wind direction bin.
            **upper_ratio_array_con** (*np.array*): Upper confidence bound of controlled energy ratio at each wind direction bin.
            **counts_ratio_array_con** (*np.array*): Counts per wind direction bin in controlled.
            **diff_array** (*np.array*): Difference in baseline and controlled energy ratio per wind direction bin.
            **lower_diff_array** (*np.array*): Lower confidence bound of difference in baseline and controlled energy ratio per wind direction bin.
            **upper_diff_array** (*np.array*): Upper confidence bound of difference in baseline and controlled energy ratio per wind direction bin.
            **counts_diff_array** (*np.array*): Counts in difference (minimum of baseline and controlled).
            **p_change_array** (*np.array*): Percent change in baseline and controlled energy ratio per wind direction bin.
            **lower_p_change_array** (*np.array*): Lower confidence bound of percent change in baseline and controlled energy ratio per wind direction bin.
            **upper_p_change_array** (*np.array*): Upper confidence bound of percent change in baseline and controlled energy ratio per wind direction bin.
            **counts_p_change_array** (*np.array*): Counts in percent change bins (minimum of baseline and controlled).

    """

    # Ensure that input arrays are np.ndarray
    reference_power_baseline = _convert_to_numpy_array(
        reference_power_baseline)
    test_power_baseline = _convert_to_numpy_array(test_power_baseline)
    wind_speed_array_baseline = _convert_to_numpy_array(
        wind_speed_array_baseline)
    wind_direction_array_baseline = _convert_to_numpy_array(
        wind_direction_array_baseline)

    reference_power_controlled = _convert_to_numpy_array(
        reference_power_controlled)
    test_power_controlled = _convert_to_numpy_array(test_power_controlled)
    wind_speed_array_controlled = _convert_to_numpy_array(
        wind_speed_array_controlled)
    wind_direction_array_controlled = _convert_to_numpy_array(
        wind_direction_array_controlled)

    # Handle no overlap specificed (assume non-overlap)
    if wind_direction_bin_p_overlap is None:
        wind_direction_bin_p_overlap = 0

    # Compute binning radius (is this right?)
    wind_direction_bin_radius = (1.0 + wind_direction_bin_p_overlap / 100.) * (
        wind_direction_bins[1]-wind_direction_bins[0])/2.0

    ratio_array_base = np.zeros(len(wind_direction_bins)) * np.nan
    lower_ratio_array_base = np.zeros(len(wind_direction_bins)) * np.nan
    upper_ratio_array_base = np.zeros(len(wind_direction_bins)) * np.nan
    counts_ratio_array_base = np.zeros(len(wind_direction_bins)) * np.nan

    ratio_array_con = np.zeros(len(wind_direction_bins)) * np.nan
    lower_ratio_array_con = np.zeros(len(wind_direction_bins)) * np.nan
    upper_ratio_array_con = np.zeros(len(wind_direction_bins)) * np.nan
    counts_ratio_array_con = np.zeros(len(wind_direction_bins)) * np.nan

    diff_array = np.zeros(len(wind_direction_bins)) * np.nan
    lower_diff_array = np.zeros(len(wind_direction_bins)) * np.nan
    upper_diff_array = np.zeros(len(wind_direction_bins)) * np.nan
    counts_diff_array = np.zeros(len(wind_direction_bins)) * np.nan

    p_change_array = np.zeros(len(wind_direction_bins)) * np.nan
    lower_p_change_array = np.zeros(len(wind_direction_bins)) * np.nan
    upper_p_change_array = np.zeros(len(wind_direction_bins)) * np.nan
    counts_p_change_array = np.zeros(len(wind_direction_bins)) * np.nan

    for i, wind_direction_bin in enumerate(wind_direction_bins):

        wind_dir_mask_baseline = (wind_direction_array_baseline >= wind_direction_bin - wind_direction_bin_radius) \
            & (wind_direction_array_baseline < wind_direction_bin + wind_direction_bin_radius)

        wind_dir_mask_controlled = (wind_direction_array_controlled >= wind_direction_bin - wind_direction_bin_radius) \
            & (wind_direction_array_controlled < wind_direction_bin + wind_direction_bin_radius)

        reference_power_baseline_wd = reference_power_baseline[wind_dir_mask_baseline]
        test_power_baseline_wd = test_power_baseline[wind_dir_mask_baseline]
        wind_speed_array_baseline_wd = wind_speed_array_baseline[wind_dir_mask_baseline]

        reference_power_controlled_wd = reference_power_controlled[wind_dir_mask_controlled]
        test_power_controlled_wd = test_power_controlled[wind_dir_mask_controlled]
        wind_speed_array_controlled_wd = wind_speed_array_controlled[wind_dir_mask_controlled]

        if (len(reference_power_baseline_wd) == 0) or (len(reference_power_controlled_wd) == 0):
            continue

        # Convert wind speed to integers
        wind_speed_array_baseline_wd = wind_speed_array_baseline_wd.astype(int)
        wind_speed_array_controlled_wd = wind_speed_array_controlled_wd.astype(
            int)

        # compute the energy ratio
        ratio_array_base[i], ratio_array_con[i], diff_array[i], p_change_array[i], counts_ratio_array_base[i], counts_ratio_array_con[i], counts_diff_array[i], counts_p_change_array[i] = energy_ratio(reference_power_baseline_wd, test_power_baseline_wd, wind_speed_array_baseline_wd,
                                                                                                                                                                                                        reference_power_controlled_wd, test_power_controlled_wd, wind_speed_array_controlled_wd)

        # Get the bounds through boot strapping
        # determine the number of bootstrap iterations if not given
        if n_boostrap is None:
            n_boostrap = _calculate_bootstrap_iterations(
                len(reference_power_baseline_wd))

        ratio_base_bs = np.zeros(n_boostrap)
        ratio_con_bs = np.zeros(n_boostrap)
        diff_bs = np.zeros(n_boostrap)
        p_change_bs = np.zeros(n_boostrap)
        for i_bs in range(n_boostrap):

            # random resampling w/ replacement
            ind_bs = np.random.randint(
                len(reference_power_baseline_wd), size=len(reference_power_baseline_wd))
            reference_power_binned_baseline = reference_power_baseline_wd[ind_bs]
            test_power_binned_baseline = test_power_baseline_wd[ind_bs]
            wind_speed_binned_baseline = wind_speed_array_baseline_wd[ind_bs]

            ind_bs = np.random.randint(
                len(reference_power_controlled_wd), size=len(reference_power_controlled_wd))
            reference_power_binned_controlled = reference_power_controlled_wd[ind_bs]
            test_power_binned_controlled = test_power_controlled_wd[ind_bs]
            wind_speed_binned_controlled = wind_speed_array_controlled_wd[ind_bs]

            # compute the energy ratio
            ratio_base_bs[i_bs], ratio_con_bs[i_bs], diff_bs[i_bs], p_change_bs[i_bs], _, _, _, _ = energy_ratio(reference_power_binned_baseline, test_power_binned_baseline, wind_speed_binned_baseline,
                                                                                                                 reference_power_binned_controlled, test_power_binned_controlled, wind_speed_binned_controlled)

        # Get the confidence bounds
        percentiles = _get_confidence_bounds(confidence)

        lower_ratio_array_base[i], upper_ratio_array_base[i] = _calculate_lower_and_upper_bound(
            ratio_base_bs, percentiles, central_estimate=ratio_array_base[i], method='simple_percentile')
        lower_ratio_array_con[i], upper_ratio_array_con[i] = _calculate_lower_and_upper_bound(
            ratio_con_bs, percentiles, central_estimate=ratio_array_con[i], method='simple_percentile')
        lower_diff_array[i], upper_diff_array[i] = _calculate_lower_and_upper_bound(
            diff_bs, percentiles, central_estimate=diff_array[i], method='simple_percentile')
        lower_p_change_array[i], upper_p_change_array[i] = _calculate_lower_and_upper_bound(
            p_change_bs, percentiles, central_estimate=p_change_array[i], method='simple_percentile')

    return ratio_array_base, lower_ratio_array_base, upper_ratio_array_base, counts_ratio_array_base, ratio_array_con, lower_ratio_array_con, upper_ratio_array_con, counts_ratio_array_con, diff_array, lower_diff_array, upper_diff_array, counts_diff_array, p_change_array, lower_p_change_array, upper_p_change_array, counts_p_change_array


def plot_energy_ratio(reference_power_baseline,
                      test_power_baseline,
                      wind_speed_array_baseline,
                      wind_direction_array_baseline,
                      reference_power_controlled,
                      test_power_controlled,
                      wind_speed_array_controlled,
                      wind_direction_array_controlled,
                      wind_direction_bins,
                      confidence=95,
                      n_boostrap=None,
                      wind_direction_bin_p_overlap=None,
                      axarr=None,
                      base_color='b',
                      con_color='g',
                      label_array=None,
                      label_pchange=None,
                      plot_simple=False,
                      plot_ratio_scatter=False,
                      marker_scale=1.
                      ):
    """
    Plot the balanced energy ratio.

    Function mainly acts as a wrapper to call 
    calculate_balanced_energy_ratio and plot the results.

    Args:
        reference_power_baseline (np.array): Array of power 
            of reference turbine in baseline conditions.
        test_power_baseline (np.array): Array of power of 
            test turbine in baseline conditions.
        wind_speed_array_baseline (np.array): Array of wind 
            speeds in baseline conditions.
        wind_direction_array_baseline (np.array): Array of 
            wind directions in baseline case.
        reference_power_controlled (np.array): Array of power 
            of reference turbine in controlled conditions.
        test_power_controlled (np.array): Array of power of 
            test turbine in controlled conditions.
        wind_speed_array_controlled (np.array): Array of wind 
            speeds in controlled conditions.
        wind_direction_array_controlled (np.array): Array of 
            wind directions in controlled case.
        wind_direction_bins (np.array): Wind directions bins.
        confidence (int, optional): Confidence level to use.  
            Defaults to 95.
        n_boostrap (int, optional): Number of bootstaps, if 
            none, _calculate_bootstrap_iterations is called.  Defaults 
            to None.
        wind_direction_bin_p_overlap (np.array, optional): 
            Percentage overlap between wind direction bin. Defaults to 
            None.
        axarr ([axes], optional): list of axes to plot to. 
            Defaults to None.
        base_color (str, optional): Color of baseline in 
            plots. Defaults to 'b'.
        con_color (str, optional): Color of controlled in 
            plots. Defaults to 'g'.
        label_array ([str], optional): List of labels to 
            apply Defaults to None.
        label_pchange ([type], optional): Label for 
            percentage change. Defaults to None.
        plot_simple (bool, optional): Plot only the ratio, no 
            confidence. Defaults to False.
        plot_ratio_scatter (bool, optional): Include scatter 
            plot of values, sized to indicate counts. Defaults to False.
        marker_scale ([type], optional): Marker scale. 
            Defaults to 1.

    """

    if axarr is None:
        fig, axarr = plt.subplots(3, 1, sharex=True)

    if label_array is None:
        label_array = ['Baseline', 'Controlled']

    if label_pchange is None:
        label_pchange = 'Percent Change'

    ratio_array_base, lower_ratio_array_base, upper_ratio_array_base, counts_ratio_array_base, ratio_array_con, lower_ratio_array_con, upper_ratio_array_con, counts_ratio_array_con, diff_array, lower_diff_array, upper_diff_array, counts_diff_array, p_change_array, lower_p_change_array, upper_p_change_array, counts_p_change_array = calculate_balanced_energy_ratio(reference_power_baseline,
                                                                                                                                                                                                                                                                                                                                                                             test_power_baseline,
                                                                                                                                                                                                                                                                                                                                                                             wind_speed_array_baseline,
                                                                                                                                                                                                                                                                                                                                                                             wind_direction_array_baseline,
                                                                                                                                                                                                                                                                                                                                                                             reference_power_controlled,
                                                                                                                                                                                                                                                                                                                                                                             test_power_controlled,
                                                                                                                                                                                                                                                                                                                                                                             wind_speed_array_controlled,
                                                                                                                                                                                                                                                                                                                                                                             wind_direction_array_controlled,
                                                                                                                                                                                                                                                                                                                                                                             wind_direction_bins,
                                                                                                                                                                                                                                                                                                                                                                             confidence=95,
                                                                                                                                                                                                                                                                                                                                                                             n_boostrap=None,
                                                                                                                                                                                                                                                                                                                                                                             wind_direction_bin_p_overlap=wind_direction_bin_p_overlap,
                                                                                                                                                                                                                                                                                                                                                                             )

    if plot_simple:
        ax = axarr[0]
        ax.plot(wind_direction_bins, ratio_array_base,
                label=label_array[0], color=base_color, ls='--')
        ax.plot(wind_direction_bins, ratio_array_con,
                label=label_array[1], color=con_color, ls='--')
        ax.axhline(1, color='k')
        ax.set_ylabel('Energy Ratio (-)')
        ax.grid(True)
        ax = axarr[1]
        # ax.plot(wind_direction_bins, p_change_array, label=label_pchange, color=con_color,ls='--')
        # ax.axhline(0,color='k')
        # ax.set_ylabel('Percent Change (%)')
        # ax.grid(True)
        ax.plot(wind_direction_bins, diff_array,
                label=label_pchange, color=con_color, ls='--')
        ax.axhline(0, color='k')
        ax.set_ylabel('Change in Energy Ratio (-)')
        ax.grid(True)
    else:

        ax = axarr[0]
        ax.plot(wind_direction_bins, ratio_array_base,
                label=label_array[0], color=base_color, ls='-', marker='.')
        ax.fill_between(wind_direction_bins, lower_ratio_array_base,
                        upper_ratio_array_base, alpha=0.3, color=base_color, label='_nolegend_')
        ax.scatter(wind_direction_bins, ratio_array_base, s=counts_ratio_array_base,
                   label='_nolegend_', color=base_color, marker='o', alpha=0.2)
        ax.plot(wind_direction_bins, ratio_array_con,
                label=label_array[1], color=con_color, ls='-', marker='.')
        ax.fill_between(wind_direction_bins, lower_ratio_array_con,
                        upper_ratio_array_con, alpha=0.3, color=con_color, label='_nolegend_')
        ax.scatter(wind_direction_bins, ratio_array_con, s=counts_ratio_array_con,
                   label='_nolegend_', color=con_color, marker='o', alpha=0.2)
        ax.axhline(1, color='k')
        ax.set_ylabel('Energy Ratio (-)')
        ax.grid(True)

        ax = axarr[1]
        # ax.plot(wind_direction_bins, p_change_array, label=label_pchange, color=con_color,ls='-',marker='.')
        # ax.fill_between(wind_direction_bins,lower_p_change_array,upper_p_change_array,alpha=0.3,color=con_color,label='_nolegend_')
        # ax.set_ylabel('Percent Change (%)')
        ax.plot(wind_direction_bins, diff_array, label=label_pchange,
                color=con_color, ls='-', marker='.')
        ax.fill_between(wind_direction_bins, lower_diff_array,
                        upper_diff_array, alpha=0.3, color=con_color, label='_nolegend_')
        ax.scatter(wind_direction_bins, diff_array, s=counts_diff_array,
                   label='_nolegend_', color=con_color, marker='o', alpha=0.2)
        ax.axhline(0, color='k')
        ax.set_ylabel('Change in Energy Ratio (-)')
        ax.grid(True)

    # return ratio_array, lower_array, upper_array, counts_array
