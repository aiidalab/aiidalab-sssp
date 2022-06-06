import json
import os

import ipywidgets as ipw
import traitlets

from aiidalab_sssp.inspect import SSSP_DB


def _load_pseudo_list(element, db=SSSP_DB) -> list:
    """Open result json file of element return list of pseudo labels
    if element is None, return empty list.
    """
    if element:
        json_fn = os.path.join(db, f"{element}.json")
        with open(json_fn, "r") as fh:
            pseudos = json.load(fh)

        return list(pseudos.keys())

    return list()


class SelectMultipleCheckbox(ipw.VBox):
    """Widget with a search field and lots of checkboxes of pseudopotentials"""

    options = traitlets.List()
    value = traitlets.List()

    def __init__(self, tick_all=True, **kwargs):
        self.tick_all = tick_all
        self.checkbox_dict = {}
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
                description=self._parse_description(desc),
                value=self.tick_all,
                style={"description_width": "initial"},
            )
            for desc in self.options
        }

        self._update_checkbox_group()

    @staticmethod
    def _parse_description(desc):
        """parse the label to more explainable line"""
        _, psp_type, psp_z, psp_tool, psp_family, *psp_version = desc.split(".")

        # parse type to details representation
        if psp_type == "nc":
            psp_type = "Norm-conserving"
        if psp_type == "us":
            psp_type = "Ultrasoft"
        if psp_type == "paw":
            psp_type = "PAW"

        out_label = f"{psp_z}\t|\t{psp_type}\t|\t{psp_family}:{psp_tool}:{'.'.join(psp_version)}"
        # if extra:
        #     out_label += f':{extra}'

        return out_label


class PseudoSelectWidget(ipw.VBox):
    element = traitlets.Unicode(allow_none=True)
    selected_pseudos = traitlets.List(allow_none=True)

    NO_ELEMENT_INFO = "No element is selected"

    def __init__(self):
        self.help_info = ipw.HTML(self.NO_ELEMENT_INFO)
        self.multiple_selection = SelectMultipleCheckbox(
            disabled=False, layout=ipw.Layout(width="98%")
        )
        self.multiple_selection.observe(
            self._on_multiple_selection_change, names="value"
        )

        super().__init__(
            children=[
                self.help_info,
                self.multiple_selection,
            ]
        )

    @traitlets.observe("element")
    def _observe_elements(self, change):
        if change["new"]:
            # if select/unselect new element update prompt help info
            self.help_info.value = (
                f"Please choose pseudopotentials of element {self.element} to inspect:"
            )

            # If an element is chosen update checkbox list
            self.pseudo_list = _load_pseudo_list(self.element)
            self.multiple_selection.options = self.pseudo_list

            # select all pseudos of element as default
            self.selected_pseudos = self.pseudo_list

    def _on_multiple_selection_change(self, change):
        self.selected_pseudos = change["new"]
