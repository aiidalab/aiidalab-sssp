# -*- coding: utf-8 -*-
"""
Adapt from aiida-sssp-workflow as prototype
Will in here refactoring it so no need to use the aiida datatype as inputs.

calculate bands distance
"""
import numpy as np
from aiida_sssp_workflow.efermi import find_efermi


def get_homo(bands, num_electrons: int):
    """
    This function only work for insulator,
    therefore the num_electrons is even number.
    """
    assert num_electrons % 2 == 0, f"There are {num_electrons} electrons, must be metal"
    # get homo band
    band = bands[:, num_electrons // 2 - 1]
    return max(band)


def fermi_dirac(band_energy, fermi_energy, smearing):
    """
    The first argument can be an array
    """
    old_settings = np.seterr(over="raise", divide="raise")
    try:
        res = 1.0 / (np.exp((band_energy - fermi_energy) / smearing) + 1.0)
    except FloatingPointError:
        res = np.heaviside(fermi_energy - band_energy, 1.0)
    np.seterr(**old_settings)

    return res


def retrieve_bands(
    bandsdata: dict,  # bands, kpoints, weights -> corresponding array
    start_band_idx,
    num_bands,
    num_electrons,
    smearing,
    do_smearing,
):
    """
    collect the bands of certain number with setting the start band.
    In order to make sure that when comparing two bands distance the number of bands is the same.

    aligh bands to fermi level

    The bands calculation of magnetic elements will giving a three dimensional bands where the
    first dimension is for the up and down spin.
    I simply concatenate along the first dimension.
    """
    bands = bandsdata.get("bands")
    weights = bandsdata.get("weights")

    # reduce by first dimension of up, down spins
    if len(bands.shape) > 2:
        nspin, nk, nbands = bands.shape
        bands = bands.reshape(nk, nbands * nspin)
        np.sort(bands)  # sort along last axis - eigenvalues of specific kpoint

    # update bands shift to fermi_level
    bands = bands - bandsdata["fermi_level"]  # shift all bands to fermi energy 0
    bands = bands[:, start_band_idx : start_band_idx + num_bands]
    bandsdata["bands"] = bands

    # update fermi_level
    if do_smearing:
        # for bands distance convergence
        # and metals in bands measure verification.
        nelectrons = num_electrons
        bands = np.asfortranarray(bands)
        meth = 2  # firmi-dirac smearing

        bandsdata["fermi_level"] = find_efermi(
            bands, weights, nelectrons, smearing, meth
        )

    else:
        # easy to spot the efermi energy only used for non-metals of typical configurations
        # in bands measure.
        homo_energy = get_homo(bands, num_electrons)
        bandsdata["fermi_level"] = homo_energy

    return bandsdata


def calculate_eta_and_max_diff(
    bandsdata_a: dict,
    bandsdata_b: dict,
    fermi_shift,
    smearing,
):
    """
    calculate the difference of two bands, weight is supported
    """
    from functools import partial

    from scipy.optimize import minimize

    weight_a = bandsdata_a.get("weights")
    weight_b = bandsdata_b.get("weights")
    weight = weight_a
    assert np.allclose(
        weight_a, weight_b
    ), "Different weight of kpoints of two calculation."

    bands_a = bandsdata_a.get("bands")
    bands_b = bandsdata_b.get("bands")

    fermi_level_a = bandsdata_a.get("fermi_level")
    fermi_level_b = bandsdata_b.get("fermi_level")

    num_bands = min(np.shape(bands_a)[1], np.shape(bands_b)[1])

    assert np.shape(bands_a)[0] == np.shape(bands_b)[0], "have different kpoints"

    # truncate the bands to same size
    bands_a = bands_a[:, : num_bands - 1]
    bands_b = bands_b[:, : num_bands - 1]

    occ_a = fermi_dirac(bands_a, fermi_level_a + fermi_shift, smearing)
    occ_b = fermi_dirac(bands_b, fermi_level_b + fermi_shift, smearing)
    occ = np.sqrt(occ_a * occ_b)

    bands_diff = bands_a - bands_b

    def fun_shift(occ, bands_diff, shift):
        # 1/w ~ degeneracy of the kpoints
        nominator = np.multiply(1 / weight[:, None], (occ * (bands_diff + shift) ** 2))
        denominator = np.multiply(1 / weight[:, None], occ)
        return np.sqrt(np.sum(nominator) / np.sum(denominator))

    # Compute eta
    eta_val = partial(fun_shift, occ, bands_diff)
    results = minimize(eta_val, np.array([0.0]), method="Nelder-Mead")
    eta = results.get("fun")
    shift = results.get("x")[0]

    # Compute max_diff:
    # then find from abs_diff the max one of which the occ > 0.5
    # first make occ > 0.5 to be 1 and occ <= 0.5 to be 0, then element-wise the
    # new occ matrix with abs_diff, and find the max diff
    abs_diff = np.abs(bands_diff + shift)
    new_occ = np.heaviside(occ - 0.5, 0.0)
    new_diff = np.multiply(abs_diff, new_occ)
    max_diff = np.amax(new_diff)

    return {
        "eta": eta,
        "shift": shift,
        "max_diff": max_diff,
    }


def get_bands_distance(
    bandsdata_a: dict,
    bandsdata_b: dict,
    smearing: float,
    fermi_shift: float,
    do_smearing: bool,
):
    """
    example of bandsdata_a -> dict = {
        "number_of_electrons": 10,
        "fermi_level": -0.97,
        "bands": <bands array> as list,
        "kpoints": <kpoints array> as list,
        "weights": <weights array> as list,
    }


    First aligh the number of two bands, e.g tranctrate the overceed nubmer of bands
    """
    # post process to deserial list to numpy arrar
    for key in ["bands", "kpoints", "weights"]:
        bandsdata_a[key] = np.asarray(bandsdata_a[key])
        bandsdata_b[key] = np.asarray(bandsdata_b[key])

    # make sure always less electrons bands as a. b hase more electrons if not equal
    if not int(bandsdata_b["number_of_electrons"]) >= int(
        bandsdata_a["number_of_electrons"]
    ):
        # swap to make sure a is less electrons pseudo
        bandsdata_a, bandsdata_b = bandsdata_b, bandsdata_a

    assert int(bandsdata_b["number_of_electrons"]) >= int(
        bandsdata_a["number_of_electrons"]
    ), f"Need to be less num_bands in a {bandsdata_a['number_of_electrons']} than b {bandsdata_b['number_of_electrons']}"

    num_electrons_a = int(bandsdata_a["number_of_electrons"])
    num_electrons_b = int(bandsdata_b["number_of_electrons"])

    # divide by 2 is valid for both spin and non-spin bands, since for spin I concatenate the bands
    # the number of bands is half of electrons
    band_b_start_band = int(num_electrons_b - num_electrons_a) // 2

    num_bands_a = bandsdata_a["number_of_bands"]
    num_bands_b = bandsdata_b["number_of_bands"] - band_b_start_band

    num_bands = min(num_bands_a, num_bands_b)

    bandsdata_a = retrieve_bands(
        bandsdata_a, 0, num_bands, num_electrons_a, smearing, do_smearing
    )

    bandsdata_b = retrieve_bands(
        bandsdata_b,
        band_b_start_band,
        num_bands,
        num_electrons_b,
        smearing,
        do_smearing,
    )

    # after cut and aligh in retrive band, the shapes are same now
    assert np.shape(bandsdata_a["bands"]) == np.shape(
        bandsdata_b["bands"]
    ), f'{np.shape(bandsdata_a["bands"])} != {np.shape(bandsdata_b["bands"])}'

    # eta_v
    fermi_shift_v = 0.0
    if do_smearing:
        smearing_v = smearing
    else:
        smearing_v = 0

    outputs = calculate_eta_and_max_diff(
        bandsdata_a, bandsdata_b, fermi_shift_v, smearing_v
    )

    _eV_to_mev = 1000
    eta_v = outputs.get("eta") * _eV_to_mev
    shift_v = outputs.get("shift") * _eV_to_mev
    max_diff_v = outputs.get("max_diff") * _eV_to_mev

    # eta_c
    # if not metal
    smearing_c = smearing
    outputs = calculate_eta_and_max_diff(
        bandsdata_a, bandsdata_b, fermi_shift, smearing_c
    )

    eta_c = outputs.get("eta") * _eV_to_mev
    shift_c = outputs.get("shift") * _eV_to_mev
    max_diff_c = outputs.get("max_diff") * _eV_to_mev

    return {
        "eta_v": eta_v,
        "shift_v": shift_v,
        "max_diff_v": max_diff_v,
        "eta_c": eta_c,
        "shift_c": shift_c,
        "max_diff_c": max_diff_c,
        "units": "meV",
    }
