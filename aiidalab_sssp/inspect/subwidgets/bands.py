import itertools
import json
import os
from pathlib import Path

import ipywidgets as ipw
import matplotlib.pyplot as plt
import numpy as np
import traitlets
from aiida_sssp_workflow.calculations.calculate_bands_distance import (
    get_bands_distance,
    retrieve_bands,
)
from aiida_sssp_workflow.utils import MAGNETIC_ELEMENTS, NONMETAL_ELEMENTS
from IPython.display import clear_output, display
from widget_bandsplot import BandsPlotWidget

from aiidalab_sssp.inspect import SSSP_DB, _px, extract_element, parse_label

# from aiidalab_sssp.inspect.band_util import get_bands_distance

_DEGAUSS = 0.045
_RY_TO_EV = 13.6056980659
_FERMI_SHIFT = 10.0  # eV in protocol FIXME also change title of plot Tab widget

_SMEARING_WIDTH = _DEGAUSS * _RY_TO_EV


def _bandview(json_path):
    """
    return bands data can directly use for bands plot widget

    :param json_path: the path to json file
    """
    try:
        with open(json_path, "r") as fh:
            data = json.load(fh)
    except Exception:
        # the bands file not exist
        data = None

    return data


class BandStructureWidget(ipw.VBox):
    """
    widget for band structure representation. When pseudos set the dropdown enabled
    for choosing pseudos for compare in one frame.
    Two dropdown for select two pseudos, but one is acceptable. If two pseudos are same
    raise warning using StatusHTML ask to select new one.
    """

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.band_structure = ipw.Output()
        self.pseudo1_select = ipw.Dropdown()
        self.pseudo2_select = ipw.Dropdown()

        self.pseudo1_select.observe(self._on_pseudo_select)
        self.pseudo2_select.observe(self._on_pseudo_select)

        super().__init__(
            children=[
                ipw.HTML("<h2> Band Structure </h2>"),
                ipw.HBox(children=[self.pseudo1_select, self.pseudo2_select]),
                self.band_structure,
            ],
        )

    @traitlets.observe("pseudos")
    def _on_pseeudos_change(self, change):
        if change["new"]:
            self.layout.visibility = "visible"
            self.pseudo1_select.options = ["None"] + list(self.pseudos.keys())
            self.pseudo2_select.options = ["None"] + list(self.pseudos.keys())
            # The first bands default select the first pseudo
            self.pseudo1_select.value = list(self.pseudos.keys())[0]
        else:
            self.layout.visibility = "hidden"

    def _on_pseudo_select(self, _):
        pseudo1_label = self.pseudo1_select.value
        pseudo1 = self.pseudos.get(pseudo1_label, None)
        pseudo2_label = self.pseudo2_select.value
        pseudo2 = self.pseudos.get(pseudo2_label, None)

        if pseudo1:
            path = pseudo1["accuracy"]["bands"]["band_structure"]
            json_path = Path.joinpath(SSSP_DB, path)

            bandsdata_a = _bandview(json_path)

        if pseudo2:
            path = pseudo2["accuracy"]["bands"]["band_structure"]
            json_path = Path.joinpath(SSSP_DB, path)

            bandsdata_b = _bandview(json_path)

        bandsdata_a, bandsdata_b = self.preprocess_on_bands(bandsdata_a, bandsdata_b)

        _band_structure_preview = BandsPlotWidget(
            bands=[bandsdata_a, bandsdata_b],
            energy_range={"ymin": -10.0, "ymax": 15.0},
        )

        with self.band_structure:
            clear_output(wait=True)
            display(_band_structure_preview)

    def preprocess_on_bands(self, bandsdata_a, bandsdata_b):
        """
        preprocess the band data before plot
        """
        # post process to deserial list to numpy arrar
        for key in ["bands", "kpoints", "weights"]:
            bandsdata_a[key] = np.asarray(bandsdata_a[key])
            bandsdata_b[key] = np.asarray(bandsdata_b[key])

        swap_flag = False
        # make sure always less electrons bands as a. b hase more electrons if not equal
        if not int(bandsdata_b["number_of_electrons"]) >= int(
            bandsdata_a["number_of_electrons"]
        ):
            # swap to make sure a is less electrons pseudo
            swap_flag = True
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

        element = extract_element(self.pseudos)
        do_smearing = element not in NONMETAL_ELEMENTS
        smearing = _SMEARING_WIDTH

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

        # swap back
        if swap_flag:
            bandsdata_a, bandsdata_b = bandsdata_b, bandsdata_a

        return bandsdata_a, bandsdata_b


class BandChessboard(ipw.VBox):
    """Band distance compare in chess board"""

    pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.chessboard = ipw.Output()

        # for caching
        self.__cache_bands = {}

        super().__init__(
            children=[
                ipw.HTML("<h2> Accuracy: Bands distance chessboard</h2>"),
                self.chessboard,
            ],
        )

    @traitlets.observe("pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.layout.visibility = "visible"
            self._render()
        else:
            self.layout.visibility = "hidden"

    def _render(self):
        """render bands chessboard side by side eta_v and eta_10"""
        _MAX_NUM = 8
        if len(self.pseudos) > _MAX_NUM:
            # Since not well render to notebook, only take 8 entities
            pseudos = {k: self.pseudos[k] for k in list(self.pseudos)[:_MAX_NUM]}
            # !!! FIXME: MUST raise warning here to ask user to toggle for more to show
        else:
            pseudos = {k: self.pseudos[k] for k in list(self.pseudos)[:]}  # all pseudos

        output = self.chessboard
        labels, arr_v, arr_c = self._bands_distance(pseudos)
        fig, (ax_v, ax_c) = plt.subplots(
            1,
            2,
            gridspec_kw={"wspace": 0.02, "hspace": 0},
            figsize=(1020 * _px, 680 * _px),
        )
        fig.canvas.header_visible = False
        self._render_plot(ax_v, ax_c, arr_v=arr_v, arr_c=arr_c, labels=labels)

        with output:
            clear_output(wait=True)
            display(fig.canvas)

    @staticmethod
    def _render_plot(ax_v, ax_c, arr_v, arr_c, labels):
        # label to concise label
        labels = [parse_label(i)["concise_label"] for i in labels]

        for idx, (ax, arr, title) in enumerate(
            [(ax_v, arr_v, r"$\eta_v$"), (ax_c, arr_c, r"$\eta_{10}$")]
        ):
            ax.imshow(arr, vmin=0, vmax=50, cmap="viridis")

            # Show all ticks and label them with the respective list entries
            # We want to show all ticks...
            ax.set_xticks(np.arange(len(labels)))
            ax.set_yticks(np.arange(len(labels)))
            # ... and label them with the respective list entries
            ax.set_xticklabels(labels)
            ax.set_yticklabels(labels)

            # specific for up side eta_v fig
            if idx == 1:
                ax.yaxis.set_visible(False)

            # Rotate the tick labels and set their alignment.
            plt.setp(
                ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor"
            )
            plt.setp(
                ax.get_yticklabels(), rotation=45, ha="right", rotation_mode="anchor"
            )

            # Loop over data dimensions and create text annotations.
            for i in range(len(labels)):
                for j in range(len(labels)):
                    ax.text(
                        j,
                        i,
                        np.around(arr[i, j], decimals=2),
                        ha="center",
                        va="center",
                        color="w",
                    )

            ax.set_title(title)

    def _bands_distance(self, pseudos):
        """compute bands distance"""
        labels = list(pseudos.keys())
        element = extract_element(pseudos)
        do_smearing = element not in NONMETAL_ELEMENTS

        fermi_shift = _FERMI_SHIFT

        arr_v = np.zeros((len(labels), len(labels)))
        arr_c = np.zeros((len(labels), len(labels)))
        for (idx1, label1), (idx2, label2) in itertools.combinations(
            enumerate(labels), 2
        ):
            # load cache if exist.
            # the pseudos passed in the function is in order, keys are sorted when created
            # Therefore, can always be '(label1)(label2)'
            cache_key = f"({label1})({label2})"
            if cache_key in self.__cache_bands:
                distance = self.__cache_bands.get(cache_key)
            else:
                bandsdata1 = _bandview(
                    os.path.join(SSSP_DB, pseudos[label1]["accuracy"]["bands"]["bands"])
                )
                bandsdata2 = _bandview(
                    os.path.join(SSSP_DB, pseudos[label2]["accuracy"]["bands"]["bands"])
                )

                spin = element is not None and element in MAGNETIC_ELEMENTS

                distance = get_bands_distance(
                    bandsdata_a=bandsdata1,
                    bandsdata_b=bandsdata2,
                    smearing=_SMEARING_WIDTH,
                    fermi_shift=fermi_shift,
                    do_smearing=do_smearing,
                    spin=spin,
                )
                self.__cache_bands[cache_key] = distance

            eta_v = distance["eta_v"]
            max_diff_v = distance["max_diff_v"]
            eta_c = distance["eta_c"]
            max_diff_c = distance["max_diff_c"]

            arr_v[idx1, idx2] = eta_v
            arr_v[idx2, idx1] = max_diff_v

            arr_c[idx1, idx2] = eta_c
            arr_c[idx2, idx1] = max_diff_c

        return labels, arr_v, arr_c
