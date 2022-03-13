import json

import ipywidgets as ipw
import traitlets

# the mock db is a folder which contains pseudos in the sub-folders named by element seprately.
# This should be some lightweight database constructed from SSSP web page and local-run aiida postgresql database
SSSP_DB = {
    "Au": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/sg15-check/result_json/Au.json",
    "Te": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/sg15-check/result_json/Te.json",
    "Na": "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/sg15-check/result_json/Na.json",
}


def _load_pseudos_from_db(db, element):
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
        _, pp_family, pp_z, pp_type, pp_version = desc.split("/")
        if pp_type == "nc":
            pp_type = "Norm-conserving"
        if pp_type == "us":
            pp_type = "Ultrasoft"
        if pp_type == "paw":
            pp_type = "PAW"

        if pp_family == "psl":
            pp_family = "PSlibrary"

        out_label = f"""{pp_z}\t|\t{pp_type}\t|\t{pp_family}-{pp_version}"""

        return out_label


class PseudoSelectWidget(ipw.VBox):
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

        # have a dict store all pseudos and their results
        self.pseudos_dict = dict()

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
            self.pseudos_dict = _load_pseudos_from_db(SSSP_DB, self.selected_element)

        self.multi_select_widget.options = (
            tuple(self.pseudos_dict.keys()) if self.pseudos_dict else tuple()
        )

        # the default when choose an element should choose all pseudos
        self.selected_pseudos = self.pseudos_dict

    def _on_multi_select_widget_change(self, change):
        selected_pseudos = dict()
        for pseudo in change["new"]:
            selected_pseudos[pseudo] = self.pseudos_dict[pseudo]
        self.selected_pseudos = selected_pseudos
