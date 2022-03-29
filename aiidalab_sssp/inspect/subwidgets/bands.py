import json

import ipywidgets as ipw
import numpy as np
import traitlets
from aiida.orm import load_node
from aiida_sssp_workflow.calculations.calculate_bands_distance import get_bands_distance
from aiida_sssp_workflow.utils import NONMETAL_ELEMENTS
from IPython.display import clear_output, display
from monty.json import jsanitize
from widget_bandsplot import BandsPlotWidget

from aiidalab_sssp.inspect.plot_utils import bands_chess


def export_bands_data(bs_dict):
    data = {}
    if "band_structure" in bs_dict:
        band_structure = load_node(bs_dict["band_structure"])
        data = json.loads(band_structure._exportcontent("json", comments=False)[0])
    if "band_parameters" in bs_dict:
        band_parameters = load_node(bs_dict["band_parameters"])
        data["fermi_level"] = band_parameters["fermi_energy"]

    return [
        jsanitize(data),
    ]


# class BandsWidget(ipw.VBox):

#     selected_pseudos = traitlets.Dict(allow_none=True)

#     def __init__(self):
#         self.bands_tab = ipw.Tab()

#         super().__init__(
#             children=[
#                 self.bands_tab,
#             ],
#         )

#     @traitlets.observe("selected_pseudos")
#     def _on_pseudos_change(self, change):
#         children = []
#         if change["new"]:
#             for idx, (label, pseudo) in enumerate(self.selected_pseudos.items()):
#                 self.bands_tab.set_title(idx, label)

#                 bands_data = export_bands_data(pseudo['bands_measure']['band_structure'])
#                 _bands_plot_view = BandsPlotWidget(
#                     bands=bands_data, dos=None, plot_fermilevel=True
#                 )
#                 out = ipw.Output()

#                 with out:
#                     import time
#                     time.sleep(0.1)
#                     display(_bands_plot_view)

#                 children.append(out)

#         self.bands_tab.children = children


def chess_compare(pseudos):
    labels = list(pseudos.keys())
    degauss = 0.045
    _RY_TO_EV = 13.6056980659

    element = list(pseudos.values())[0]["pseudo_info"]["element"]
    is_metal = element not in NONMETAL_ELEMENTS

    fermi_shift = 5  # eV in protocol FIXME

    arr_lst_c = []
    arr_lst_v = []
    for a in labels:

        inner_list_c = []
        inner_list_v = []
        for b in labels:
            bands_a = load_node(pseudos[a]["bands_measure"]["bands"]["band_structure"])
            bands_b = load_node(pseudos[b]["bands_measure"]["bands"]["band_structure"])
            band_parameters_a = load_node(
                pseudos[a]["bands_measure"]["bands"]["band_parameters"]
            )
            band_parameters_b = load_node(
                pseudos[b]["bands_measure"]["bands"]["band_parameters"]
            )
            res = get_bands_distance(
                bands_a,
                bands_b,
                band_parameters_a,
                band_parameters_b,
                smearing=degauss * _RY_TO_EV,
                fermi_shift=fermi_shift,
                is_metal=is_metal,
            )
            eta_v = res["eta_v"]
            max_diff_v = res["max_diff_v"]

            eta_c = res["eta_c"]
            max_diff_c = res["max_diff_c"]

            if a < b:
                inner_list_c.append(eta_c)
                inner_list_v.append(eta_v)
            else:
                inner_list_c.append(max_diff_c)
                inner_list_v.append(max_diff_v)

        arr_lst_c.append(inner_list_c)
        arr_lst_v.append(inner_list_v)

    cross_arr_c = np.array(arr_lst_c)
    cross_arr_v = np.array(arr_lst_v)

    return labels, cross_arr_c, cross_arr_v


class BandsWidget(ipw.VBox):

    selected_pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.bands_out = ipw.Output()
        self.select = ipw.Dropdown()
        self.chess_out = ipw.Output()

        self.select.observe(self._on_select, names="value")

        super().__init__(
            children=[
                ipw.HTML("Band structure"),
                self.select,
                self.bands_out,
                ipw.HTML(
                    "Bands distance, upper triangle->eta, lower->max_diff"
                ),  # FIXME recheck
                self.chess_out,
            ],
        )

    @traitlets.observe("selected_pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.select.options = [i for i in self.selected_pseudos.keys()]
            labels, cross_arr_c, cross_arr_v = chess_compare(change["new"])

            fig = bands_chess(labels, cross_arr_c, cross_arr_v)

            with self.chess_out:
                clear_output()
                fig.canvas.header_visible = False
                display(fig.canvas)

    def _on_select(self, change):

        if change["new"]:
            label = change["new"]
            pseudo = self.selected_pseudos[label]

            bands_data = export_bands_data(pseudo["bands_measure"]["band_structure"])
            _bands_plot_view = BandsPlotWidget(
                bands=bands_data, dos=None, plot_fermilevel=True
            )

            with self.bands_out:
                clear_output()
                display(_bands_plot_view)
