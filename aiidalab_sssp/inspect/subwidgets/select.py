import json

import ipywidgets as ipw
import traitlets

# the mock db is a folder which contains pseudos in the sub-folders named by element seprately.
# This should be some lightweight database constructed from SSSP web page and local-run aiida postgresql database
SSSP_JSON = {
    "Mg": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/demo_results/results/Mg.json",
    "Si": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/demo_results/results/Si.json",
}
SSSP_ARCHIVE = {
    "Mg": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/demo_results/results/Mg.aiida",
    "Si": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/demo_results/results/Si.aiida",
}


def _load_pseudos_from_json(db, element):
    from urllib import request

    pseudos_url = db.get(element, None)

    if pseudos_url:
        with request.urlopen(pseudos_url) as url:
            pseudos = json.loads(url.read().decode())
    else:
        return None

    return pseudos


class SelectMultipleCheckbox(ipw.VBox):
    """Widget with a search field and lots of checkboxes"""

    options = traitlets.List()
    value = traitlets.List()

    def __init__(self, tick_all=True, **kwargs):
        self.tick_all = tick_all
        self.checkbox_dict = {
            f"{desc}": ipw.Checkbox(
                description=self._parse_desc(desc),
                value=self.tick_all,
                style={"description_width": "initial"},
            )
            for desc in self.options
        }
        self._update_checkbox_group()

        super().__init__(children=list(self.checkbox_dict.values()), **kwargs)

    def _update_checkbox_group(self):
        # Update the checkbox widgets view
        self.children = list(self.checkbox_dict.values())
        # Since all checkboxes are recreated set the observe for all off them
        for checkbox in self.checkbox_dict.values():
            checkbox.observe(self._on_any_checkbox_change, names="value")

        # reset the outpput values
        self._reset_value()

    def _on_any_checkbox_change(self, change):
        # Any time any checkbox ticked or unticked reset
        self._reset_value()

    def _reset_value(self):
        self.value = [
            label for label, checkbox in self.checkbox_dict.items() if checkbox.value
        ]

    @traitlets.observe("options")
    def _observe_options_change(self, change):
        # when options list (element rechoose) change update all checkboxes
        self.checkbox_dict = {
            f"{desc}": ipw.Checkbox(
                description=self._parse_desc(desc),
                value=self.tick_all,
                style={"description_width": "initial"},
            )
            for desc in self.options
        }

        self._update_checkbox_group()

    @staticmethod
    def _parse_desc(desc):
        """parse the label to more explainable line"""
        _, psp_type, psp_z, psp_family, psp_version = desc.split("/")[0:5]
        if psp_type == "nc":
            psp_type = "Norm-conserving"
        if psp_type == "us":
            psp_type = "Ultrasoft"
        if psp_type == "paw":
            psp_type = "PAW"

        if psp_family == "psl":
            psp_family = "PSlibrary"
        if psp_family == "dojo":
            psp_family = "DOJO"
        if psp_family == "sg15":
            psp_family = "SG15"

        out_label = f"""{psp_z}\t|\t{psp_type}\t|\t{psp_family}-{psp_version}"""

        return out_label


class PseudoSelectWidget(ipw.VBox):
    pseudos_dict = traitlets.Dict(allow_none=True)
    selected_element = traitlets.Unicode(allow_none=True)
    selected_pseudos = traitlets.Dict(allow_none=True)

    NO_ELEMENT_INFO = "No element is selected"

    def __init__(self):
        self.help_info = ipw.HTML(self.NO_ELEMENT_INFO)
        self.multi_select_widget = SelectMultipleCheckbox(
            disabled=False, layout=ipw.Layout(width="98%")
        )
        self.multi_select_widget.observe(
            self._on_multi_select_widget_change, names="value"
        )

        super().__init__(
            children=[
                self.help_info,
                self.multi_select_widget,
            ]
        )

    @traitlets.observe("selected_element")
    def _observe_selected_elements(self, change):
        if change["new"]:
            # if the element is selected, get the element
            self.help_info.value = f"Please choose pseudopotentials of element {self.selected_element} to inspect:"

        if self.selected_element:
            self.pseudos_dict = _load_pseudos_from_json(
                SSSP_JSON, self.selected_element
            )

        self.multi_select_widget.options = (
            tuple(self.pseudos_dict.keys()) if self.pseudos_dict else tuple()
        )

        # the default when choose an element should choose all pseudos
        self.selected_pseudos = self.pseudos_dict

    def _on_multi_select_widget_change(self, change):
        pseudos = dict()
        for pseudo in change["new"]:
            pseudos[pseudo] = self.pseudos_dict[pseudo]
        self.selected_pseudos = pseudos

    @traitlets.observe("pseudos_dict")
    def _observe_selected_pseudos(self, _):
        self.multi_select_widget.options = (
            tuple(self.pseudos_dict.keys()) if self.pseudos_dict else tuple()
        )
