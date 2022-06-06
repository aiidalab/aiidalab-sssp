import json
import os

import ipywidgets as ipw
import traitlets

from aiidalab_sssp.inspect import SSSP_DB, parse_label


def _load_pseudos(element, db=SSSP_DB) -> dict:
    """Open result json file of element return as dict"""
    if element:
        json_fn = os.path.join(db, f"{element}.json")
        with open(json_fn, "r") as fh:
            pseudos = json.load(fh)

        return pseudos

    return dict()


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
                description=parse_label(desc)["representive_label"],
                value=self.tick_all,
                style={"description_width": "initial"},
            )
            for desc in self.options
        }

        self._update_checkbox_group()


class PseudoSelectWidget(ipw.VBox):
    element = traitlets.Unicode(allow_none=True)
    selected_pseudos = traitlets.Dict(allow_none=True)

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
            # self.pseudos store all dict for the element the initial parsed from element json
            self.pseudos = _load_pseudos(self.element)
            self.multiple_selection.options = list(self.pseudos.keys())

            # select all pseudos of element as default
            self.selected_pseudos = self.pseudos

    def _on_multiple_selection_change(self, change):
        self.selected_pseudos = {k: self.pseudos[k] for k in change["new"]}
