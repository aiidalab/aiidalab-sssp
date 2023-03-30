import ipywidgets as ipw
import traitlets

from aiidalab_sssp.inspect import parse_label

BASE_DOWNLOAD_URL = (
    "https://raw.githubusercontent.com/unkcpz/sssp-verify-scripts/main/libraries-pbe"
)



class SelectMultipleCheckbox(ipw.VBox):
    """Widget with a search field and lots of checkboxes of pseudopotentials"""

    options = traitlets.List()  # options for all labels
    selected_labels = traitlets.List()  # labels selected

    def __init__(self, tick_all=True, **kwargs):
        self.tick_all = tick_all
        self.checkbox_dict = {}
        self._update_checkbox_group()

        super().__init__(**kwargs)

    def dw_btn(self, label):
        """From label generate a redirect button to upf source"""
        if "dojo.v4-std" in label:
            lib_folder = "NC-DOJOv4-standard"
        elif "dojo.v4-str" in label:
            lib_folder = "NC-DOJOv4-stringent"
        elif "sg15.v0" in label:
            lib_folder = "NC-SG15-ONCVPSP4"
        elif "psl.v0." in label and "paw" in label:
            lib_folder = "PAW-PSL0.x"
        elif "psl.v0." in label and "us" in label:
            lib_folder = "US-PSL0.x"
        elif "psl.v1.0.0-high" in label and "paw" in label:
            lib_folder = "PAW-PSL1.0.0-high"
        elif "psl.v1.0.0-low" in label and "paw" in label:
            lib_folder = "PAW-PSL1.0.0-low"
        elif "psl.v1.0.0-high" in label and "us" in label:
            lib_folder = "US-PSL1.0.0-high"
        elif "psl.v1.0.0-low" in label and "us" in label:
            lib_folder = "US-PSL1.0.0-low"
        elif "jth.v1.1-std" in label:
            lib_folder = "PAW-JTH1.1-standard"
        elif "jth.v1.1-str" in label:
            lib_folder = "PAW-JTH1.1-stringent"
        elif "gbrv" in label:
            lib_folder = "US-GBRV-1.x"
        elif "wentzcovitch" in label and "neo" in label:
            lib_folder = "PAW-RE-Wentzcovitch/neo"
        elif "wentzcovitch" in label and "legacy" in label:
            lib_folder = "PAW-RE-Wentzcovitch/legacy"
        else:
            lib_folder = "UNCATOGRIZED"

        btn = ipw.HTML(
            f"""<a href="{BASE_DOWNLOAD_URL}/{lib_folder}/{label}.upf" target="_blank">➥</a>"""
        )

        return btn

    def _update_checkbox_group(self):
        # Update the checkbox widgets view
        self.children = [
            ipw.HBox(children=[v, self.dw_btn(k)], layout=ipw.Layout(width="55%"))
            for k, v in self.checkbox_dict.items()
        ]

        # Since all checkboxes are recreated set the observe for all of them
        for checkbox in self.checkbox_dict.values():
            checkbox.observe(self._on_any_checkbox_change, names="value")

        # reset the outpput values
        self._update_selected_labels()

    def _on_any_checkbox_change(self, change):
        # Any time any checkbox ticked or unticked reset
        self._update_selected_labels()

    def _update_selected_labels(self):
        self.selected_labels = [
            label for label, checkbox in self.checkbox_dict.items() if checkbox.value
        ]

    def unselecet_all(self):
        with self.hold_trait_notifications():
            for key in self.checkbox_dict.keys():
                self.checkbox_dict[key].value = False

        self._update_selected_labels()

    def selecet_all(self):
        with self.hold_trait_notifications():
            for key in self.checkbox_dict.keys():
                self.checkbox_dict[key].value = True

        self._update_selected_labels()

    @traitlets.observe("options")
    def _observe_options_change(self, change):
        # when options list (element rechoose) change update all checkboxes
        self.checkbox_dict = {
            f"{desc}": ipw.Checkbox(
                description=parse_label(desc)["representive_label"],
                value=self.tick_all,
                style={"description_width": "initial"},
                layout=ipw.Layout(width="50%", height="50%"),
            )
            for desc in self.options
        }

        self._update_checkbox_group()


class PseudoSelectWidget(ipw.VBox):
    # (input) all pseudos of a element, the whole dict from json fixed once element choosen
    pseudos = traitlets.Dict(allow_none=True)   
    
    # (output) selected pseudos of a element, the whole dict once pseudos selected
    selected_pseudos = traitlets.Dict(allow_none=True)

    def __init__(self):
        self.NO_PSEUDOS_FOR_SELECT_INFO = "No pseudopotentials available for compare, please select an element or upload a verification file."
        self.help_info = ipw.HTML(self.NO_PSEUDOS_FOR_SELECT_INFO)
        self.unselect_all = ipw.Button(
            description="Unselect All",
            button_style="info",
        )
        self.unselect_all.on_click(self._unselect_all_click)

        self.select_all = ipw.Button(
            description="Select All",
            button_style="info",
        )
        self.select_all.on_click(self._on_select_all_click)

        self.select_buttons = ipw.HBox(children=[self.unselect_all, self.select_all])
        self.select_buttons.layout.display = "none"

        self.multiple_selection = SelectMultipleCheckbox(
            disabled=False, layout=ipw.Layout(width="98%")
        )
        self.multiple_selection.observe(
            self._on_multiple_selection_change, names="selected_labels"
        )

        super().__init__(
            children=[
                self.help_info,
                self.select_buttons,
                self.multiple_selection,
            ]
        )

    def _unselect_all_click(self, _):
        """Unselect all"""
        # self.selected_pseudos = {}
        self.multiple_selection.unselecet_all()

    def _on_select_all_click(self, _):
        """Selecet All"""
        # self.selected_pseudos = _load_pseudos(self.element)
        self.multiple_selection.selecet_all()

    @traitlets.observe("pseudos")
    def _observe_pseudos(self, change):
        if change["new"] is not None and change["new"] != {}:  # pseudos is not empty
            self.select_buttons.layout.display = "flex"  # show select/unselect all buttons
            # if select/unselect new element update prompt help info
            self.help_info.value = (
                f"Please choose pseudopotentials to inspect:"
            )

            # self.pseudos store all dict for the element the initial parsed from element json
            # select all pseudos of element as default
            self.multiple_selection.options = list(self.pseudos.keys())
            self.selected_pseudos = self.pseudos.copy()    # the traitlets need to be a copy of the dict otherwise it will not trigger the change event
        else:
            # if empty dict passed (by unseleted the element) reset multiple select widget
            self.reset()

    def _on_multiple_selection_change(self, change):
        self.selected_pseudos = {
            k: self.pseudos[k] for k in sorted(change["new"], key=str.lower)
        }

    def reset(self):
        """Reset the widget to initial state, no checkbox widget at all"""
        self.select_buttons.layout.visibility = "hidden"
        self.help_info.value = self.NO_PSEUDOS_FOR_SELECT_INFO
        self.multiple_selection.options = list()
        self.selected_pseudos = {}
