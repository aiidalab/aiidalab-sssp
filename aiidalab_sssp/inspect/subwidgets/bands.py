import json

import ipywidgets as ipw
import traitlets
from aiida.orm import load_node
from IPython.display import clear_output, display
from monty.json import jsanitize
from widget_bandsplot import BandsPlotWidget


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


class BandsWidget(ipw.VBox):

    selected_pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.bands_out = ipw.Output()
        self.select = ipw.Dropdown()

        self.select.observe(self._on_select, names="value")

        super().__init__(
            children=[
                self.select,
                self.bands_out,
            ],
        )

    @traitlets.observe("selected_pseudos")
    def _on_pseudos_change(self, change):
        if change["new"]:
            self.select.options = [i for i in self.selected_pseudos.keys()]

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
