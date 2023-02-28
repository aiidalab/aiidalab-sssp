"""widget for pseudo inmport"""
import io
import os

import ipywidgets as ipw
import traitlets
from aiida import orm
from aiida.common import NotExistent
from aiida.engine import ProcessState
from aiida.orm import Node, load_code, load_node
from aiida.plugins import DataFactory, WorkflowFactory
from aiida_sssp_workflow.workflows.verifications import DEFAULT_PROPERTIES_LIST
from aiidalab_widgets_base import (
    ComputationalResourcesWidget,
    ProcessMonitor,
    ProcessNodesTreeWidget,
    WizardAppWidgetStep,
    viewer,
)
from IPython.display import clear_output, display

from aiidalab_sssp.parameters import DEFAULT_PARAMETERS

UpfData = DataFactory("pseudo.upf")
VerificationWorkChain = WorkflowFactory("sssp_workflow.verification")


class PseudoUploadWidget(ipw.VBox):
    """Class that allows to upload pseudopotential from user's computer."""

    pseudo = traitlets.Tuple()
    error_message = traitlets.Unicode()

    def __init__(self, title="", description="Upload Pseudopotential"):
        self.title = title
        self.file_upload = ipw.FileUpload(
            description=description, multiple=False, layout={"width": "initial"}
        )
        supported_formats = ipw.HTML(
            """<a href="http://www.quantum-espresso.org/pseudopotentials/
unified-pseudopotential-format" target="_blank">
Supported pseudo formats (Now only support UPF type)
</a>"""
        )
        self.file_upload.observe(self._on_file_upload, names="value")
        self.error_message = ""
        super().__init__(children=[self.file_upload, supported_formats])

    def _on_file_upload(self, change=None):
        """When file upload button is pressed."""
        fname, item = next(iter(change["new"].items()))
        try:
            content = item["content"]

            # Order matters make sure when pseudo change
            # the pseudo_filename is set
            with self.hold_trait_notifications():
                self.pseudo = (fname, UpfData(io.BytesIO(content)))
        except ValueError:
            self.error_message = (
                "wrong pseudopotential file type. (Only UPF support now)"
            )


class PseudoSelectionStep(ipw.VBox, WizardAppWidgetStep):
    """
    Upload a pesudopotential and store it as UpfData in database
    """

    confirmed_pseudo = traitlets.Tuple(allow_none=True)

    def __init__(self, **kwargs):
        self.pseudo_upload = PseudoUploadWidget()
        self.pseudo_upload.observe(self._observe_pseudo_upload, "pseudo")

        self.description = ipw.HTML(
            """
            <p>Select a pseudopotential from one of the following sources and then
            click "Confirm" to go to the next step.</p><i class="fa fa-exclamation-circle"
            aria-hidden="true"></i> Currently only UPF pseudopotential file are
            supported.
            """
        )

        self.pseudo_text = ipw.Text(
            placeholder="[No pseudo selected]",
            description="Selected:",
            disabled=True,
            layout=ipw.Layout(width="auto"),
        )

        self.confirm_button = ipw.Button(
            description="Confirm",
            tooltip="Confirm the currently selected pseudopotential and go to the next step.",
            button_style="success",
            icon="check-circle",
            disabled=True,
            layout=ipw.Layout(width="auto"),
        )
        self.confirm_button.on_click(self.confirm)
        self.message_area = ipw.HTML()

        super().__init__(
            children=[
                self.description,
                self.pseudo_upload,
                self.pseudo_text,
                self.message_area,
                self.confirm_button,
            ],
            **kwargs,
        )

    @traitlets.default("state")
    def _default_state(self):
        return self.State.INIT

    def _update_state(self):
        if self.pseudo_text is None:
            self.state = self.State.READY
        else:
            if self.confirmed_pseudo:
                self.state = self.State.SUCCESS
                self.confirm_button.disabled = True
            else:
                self.state = self.State.CONFIGURED
                self.confirm_button.disabled = False

    def _observe_pseudo_upload(self, _):
        with self.hold_trait_notifications():
            if self.pseudo_upload.pseudo is None:
                self.message_area.value = self.pseudo_upload.error_message
            else:
                # Upload then set pseudo and show filename on text board
                self.pseudo_text.value = self.pseudo_upload.pseudo[0]

                if self.pseudo_upload.error_message:
                    self.message_area.value = self.pseudo_upload.error_message

            self._update_state()

    @traitlets.observe("confirmed_pseudo")
    def _observe_confirmed_pseudo(self, _):
        with self.hold_trait_notifications():
            self._update_state()

    def can_reset(self):
        return self.confirmed_pseudo is not None

    def confirm(self, _=None):
        self.confirmed_pseudo = self.pseudo_upload.pseudo

        self._update_state()

    def reset(self):  # unconfirm
        self.confirmed_pseudo = None

        self._update_state()


class WorkChainSettings(ipw.VBox):

    calc_type_help = ipw.HTML(
        """<div style="line-height: 140%; padding-top: 6px; padding-bottom: 0px">
        The acwf protocol is used to set the parameters used for pseudopotential
        verification.
        The acwf calculation protocol represents a set of parameters compatible
        with aiida-common-workflow.
        Three different calculation type are provided for verification,
        <ol style="list-style-type:none">
            <li style="padding-top: 2px; padding-bottom: 2px;">⚙️ <b>Standard:</b> production mode that run verification on a thourgh cutoff test.</li>
            <li style="padding-top: 2px; padding-bottom: 2px;">⚙️ <b>Quick:</b> quick mode is design to run quickly with sparse cutoff test sample points.</li>
            <li style="padding-top: 2px; padding-bottom: 2px;">🔍  <b>Precheck:</b> precheck is for running a pre-check verification to decide whether 200 Ry as reference is enough if not it is not valuable to run futher verification on smaller cutoff and whether small referece cutoff can be used for production verification.</li>
        </ol>
        The criteria determine when the wavefunction and
        charge density cutoff tests are converged.
        Choose the "efficiency" protocol for cutoff test to give a efficiency
        pseudopotential. The "precision" protocol that provides more
        accuracy pseudopotential but will take longer.
        </div>"""
    )
    properties_list = traitlets.List()

    def __init__(self, **kwargs):

        # Accuracy properties
        self.delta_measure = ipw.Checkbox(
            description="",
            tooltip="Calculate the delta measure w.r.t AE.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.bands_measure = ipw.Checkbox(
            description="",
            tooltip="Calculate the bands measure for bands distance and bandstructure.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )

        self.delta_measure.observe(self._update_properties_list, "value")
        self.bands_measure.observe(self._update_properties_list, "value")

        # Convergenece properties
        self.cohesive_energy_convergence = ipw.Checkbox(
            description="",
            tooltip="Convergence test on cohesive energy.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.pressure_convergence = ipw.Checkbox(
            description="",
            tooltip="Convergence test on pressue.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.phonon_frequencies_convergence = ipw.Checkbox(
            description="",
            tooltip="Convergence test on phonon frequencies.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.delta_convergence = ipw.Checkbox(
            description="",
            tooltip="Convergence test on delta factor.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.bands_convergence = ipw.Checkbox(
            description="",
            tooltip="Convergence test on bands distance.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )

        self.cohesive_energy_convergence.observe(self._update_properties_list, "value")
        self.pressure_convergence.observe(self._update_properties_list, "value")
        self.phonon_frequencies_convergence.observe(
            self._update_properties_list, "value"
        )
        self.delta_convergence.observe(self._update_properties_list, "value")
        self.bands_convergence.observe(self._update_properties_list, "value")

        self.properties_list = DEFAULT_PROPERTIES_LIST

        # Work chain calc_type
        self.calc_type = ipw.ToggleButtons(
            options=["standard", "quick", "precheck"],
            value="standard",
        )

        self.criteria = ipw.ToggleButtons(
            options=["efficiency", "precision"],
            value="efficiency",
        )

        super().__init__(
            children=[
                ipw.HTML("Properties to verified - For accuracy of pseudopotential:"),
                ipw.HBox(
                    children=[ipw.HTML("<b>Delta measure</b>"), self.delta_measure]
                ),
                ipw.HBox(
                    children=[ipw.HTML("<b>Bands measure</b>"), self.bands_measure]
                ),
                ipw.HTML(
                    "Properties to verified - For convergence of pseudopotential:"
                ),
                ipw.HBox(
                    children=[
                        ipw.HTML("<b>Convergence: cohesive energy</b>"),
                        self.cohesive_energy_convergence,
                    ]
                ),
                ipw.HBox(
                    children=[
                        ipw.HTML("<b>Convergence: phonon frequencies</b>"),
                        self.phonon_frequencies_convergence,
                    ]
                ),
                ipw.HBox(
                    children=[
                        ipw.HTML("<b>Convergence: pressure</b>"),
                        self.pressure_convergence,
                    ]
                ),
                ipw.HBox(
                    children=[
                        ipw.HTML("<b>Convergence: delta</b>"),
                        self.delta_convergence,
                    ]
                ),
                ipw.HBox(
                    children=[
                        ipw.HTML("<b>Convergence: bands</b>"),
                        self.bands_convergence,
                    ]
                ),
                # calculation type setup
                self.calc_type_help,
                ipw.HTML(
                    "Select calculation type:",
                    layout=ipw.Layout(flex="1 1 auto"),
                ),
                self.calc_type,
                ipw.HTML("Select criteria:", layout=ipw.Layout(flex="1 1 auto")),
                self.criteria,
            ],
            **kwargs,
        )

    def _update_properties_list(self, _):
        lst = []
        if self.delta_measure.value:
            lst.append("accuracy.delta")

        if self.bands_measure.value:
            lst.append("accuracy.bands")

        if self.cohesive_energy_convergence.value:
            lst.append("convergence.cohesive_energy")

        if self.phonon_frequencies_convergence.value:
            lst.append("convergence.phonon_frequencies")

        if self.pressure_convergence.value:
            lst.append("convergence.pressure")

        if self.delta_convergence.value:
            lst.append("convergence.delta")

        if self.bands_convergence.value:
            lst.append("convergence.bands")

        self.properties_list = lst


class ConfigureSsspWorkChainStep(ipw.VBox, WizardAppWidgetStep):

    confirmed = traitlets.Bool()
    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    workchain_settings = traitlets.Instance(WorkChainSettings, allow_none=True)

    def __init__(self, **kwargs):
        self.workchain_settings = WorkChainSettings()
        self.workchain_settings.delta_measure.observe(self._update_state, "value")
        self.workchain_settings.bands_measure.observe(self._update_state, "value")
        self.workchain_settings.cohesive_energy_convergence.observe(
            self._update_state, "value"
        )
        self.workchain_settings.phonon_frequencies_convergence.observe(
            self._update_state, "value"
        )
        self.workchain_settings.pressure_convergence.observe(
            self._update_state, "value"
        )
        self.workchain_settings.bands_convergence.observe(self._update_state, "value")
        self.workchain_settings.delta_convergence.observe(self._update_state, "value")

        self._submission_blocker_messages = ipw.HTML()

        self.confirm_button = ipw.Button(
            description="Confirm",
            tooltip="Confirm the currently selected settings and go to the next step.",
            button_style="success",
            icon="check-circle",
            disabled=True,
            layout=ipw.Layout(width="auto"),
        )

        self.confirm_button.on_click(self.confirm)

        super().__init__(
            children=[
                self.workchain_settings,
                self._submission_blocker_messages,
                self.confirm_button,
            ],
            **kwargs,
        )

    @traitlets.observe("previous_step_state")
    def _observe_previous_step_state(self, change):
        self._update_state()

    def set_input_parameters(self, parameters):
        """Set the inputs in the GUI based on a set of parameters."""
        with self.hold_trait_notifications():
            # Wor chain settings
            self.workchain_settings.delta_measure.value = parameters["delta_measure"]
            self.workchain_settings.bands_measure.value = parameters["bands_measure"]
            self.workchain_settings.cohesive_energy_convergence.value = parameters[
                "cohesive_energy_convergence"
            ]
            self.workchain_settings.phonon_frequencies_convergence.value = parameters[
                "phonon_frequencies_convergence"
            ]
            self.workchain_settings.pressure_convergence.value = parameters[
                "pressure_convergence"
            ]
            self.workchain_settings.delta_convergence.value = parameters[
                "delta_convergence"
            ]
            self.workchain_settings.bands_convergence.value = parameters[
                "bands_convergence"
            ]
            self.workchain_settings.criteria.value = parameters["criteria"]
            self.workchain_settings.calc_type.value = parameters["calc_type"]

    def _update_state(self, _=None):
        if self.previous_step_state == self.State.SUCCESS:
            self.confirm_button.disabled = False
            if not (
                self.workchain_settings.delta_measure.value
                or self.workchain_settings.bands_measure.value
                or self.workchain_settings.cohesive_energy_convergence.value
                or self.workchain_settings.phonon_frequencies_convergence.value
                or self.workchain_settings.pressure_convergence.value
                or self.workchain_settings.delta_convergence.value
                or self.workchain_settings.bands_convergence.value
            ):
                self.confirm_button.disabled = True
                self.state = self.State.READY
                self._submission_blocker_messages.value = """
                    <div class="alert alert-info">
                    The configured work chain would not actually compute anything.
                    Select either at least one of the
                    the delta measure or the convergence calculations or both.</div>"""
            else:
                self._submission_blocker_messages.value = ""
                self.state = self.State.CONFIGURED
        elif self.previous_step_state == self.State.FAIL:
            self.state = self.State.FAIL
        else:
            self.confirm_button.disabled = True
            self.state = self.State.INIT
            self.set_input_parameters(DEFAULT_PARAMETERS)

    def confirm(self, _None):
        self.confirm_button.disabled = True
        self.state = self.State.SUCCESS

    @traitlets.default("state")
    def _default_state(self):
        return self.State.INIT

    def reset(self):
        with self.hold_trait_notifications():
            self.set_input_parameters(DEFAULT_PARAMETERS)


class MetadataSettings(ipw.VBox):
    """
    This is the widget for storing the settings of pseudopotential
    metadata. The part of the metadatas can be read from the input
    pseudopotential file. User also allowed to set or modified them.
    It will impact the primary key of how the verification result is
    stored.

    Currently the primary key simply a string has the format:
        <element>.<psp_type>.<z_valence>.<psp_tool>.<psp_family>.<psp_version>.<psp_extra_label>

    In the future this should be a formatted class of data that can be used
    to identify the pseudopotentials.
    """

    pseudo = traitlets.Tuple(allow_none=True)
    output_metadata = traitlets.Dict()

    def __init__(self, **kwargs):
        extra = {
            "style": {"description_width": "180px"},
            "layout": {"min_width": "310px"},
        }

        self.family = ipw.Text(
            placeholder="Unresolved",
            description="Pseudopotential family:",
            **extra,
        )
        self.gen_tool = ipw.Text(
            placeholder="Unresolved",
            description="Pseudopotential tool:",
            **extra,
        )
        self.version = ipw.Text(
            placeholder="Unresolved",
            description="Pseudopotential version:",
            **extra,
        )

        self.family.observe(self._on_tag_change)
        self.gen_tool.observe(self._on_tag_change)
        self.version.observe(self._on_tag_change)

        self.description = ipw.Textarea(
            placeholder="Optional",
            description="Description:",
            **extra,
        )

        super().__init__(
            children=[
                self.family,
                self.gen_tool,
                self.version,
                self.description,
            ],
            **kwargs,
        )

    def _on_tag_change(self, _):
        """family/gen_tool/version/extra change. reset output label"""
        self.output_metadata["family"] = self.family.value
        self.output_metadata["tool"] = self.gen_tool.value
        self.output_metadata["version"] = self.version.value

    @traitlets.observe("pseudo")
    def _observe_pseudo(self, _):
        from pseudo_parser.upf_parser import parse

        from aiidalab_sssp.inspect import parse_label

        try:
            # when upload a standard named input
            label = ".".join(self.pseudo[0].split(".")[:-1])
            label_dict = parse_label(label)
        except IndexError:
            # tuple index out of range. Pseudo not upload yet.
            self.output_metadata = {}
        except Exception:
            # when upload a non-standard named input upf
            pseudo_info = parse(self.pseudo[1].get_content())

            self.output_metadata = {
                "element": pseudo_info["element"],
                "type": pseudo_info["pp_type"],
                "z_valence": pseudo_info["z_valence"],
                "family": self.family.value,
                "tool": self.gen_tool.value,
                "version": self.version.value,
            }
        else:
            self.output_metadata = {
                "element": label_dict["element"],
                "type": label_dict["type"],
                "z_valence": label_dict["z"],
                "family": label_dict["family"],
                "tool": label_dict["tool"],
                "version": label_dict["version"],
            }
            self.family.value = label_dict["family"]
            self.gen_tool.value = label_dict["tool"]
            self.version.value = label_dict["version"]


class SettingPseudoMetadataStep(ipw.VBox, WizardAppWidgetStep):
    """setting the extra metadata for the future query and description display of the pseudo"""

    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    pseudo = traitlets.Tuple(allow_none=True)
    confirmed = traitlets.Bool()
    output_label = traitlets.Unicode()

    metadata_help = ipw.HTML(
        """<div style="line-height:120%; padding-top:10px;">
        <p>There is no general rule of thumb on how to name the extra metadata. </p>
        <p>The family and version field deduct from input pseudopotential.</p>
        <p>In general:</p>
        <ul>
        <li>family indicate the library, sg15, gbrv etc.</li>
        <li>version of library.</li>
        <li>tool used to generate pseudopotential.</li>
        <li>extra label is optional append to the label.</li>
        <li>description of node.</li>
        </ul>
        </div>"""
    )

    _TITLE_PLACEHODER = "<p>No pseudopotential detect</p>"

    def __init__(self, **kwargs):
        self.title = ipw.HTML(self._TITLE_PLACEHODER)

        self.metadata_settings = MetadataSettings()
        self.metadata_settings.observe(self._on_metadata_settings_change)

        self._submission_blocker_messages = ipw.HTML()

        self.confirm_button = ipw.Button(
            description="Confirm",
            tooltip="Confirm the currently metadata settings and go to the next step.",
            button_style="success",
            icon="check-circle",
            disabled=True,
            layout=ipw.Layout(width="auto"),
        )

        self.confirm_button.on_click(self.confirm)

        super().__init__(
            children=[
                self.title,
                ipw.HBox(
                    children=[self.metadata_settings, self.metadata_help],
                    layout=ipw.Layout(justify_content="space-between"),
                ),
                self._submission_blocker_messages,
                self.confirm_button,
            ],
            **kwargs,
        )

    @traitlets.observe("pseudo")
    def _on_pseudo_change(self, _):
        self.metadata_settings.pseudo = self.pseudo
        self._update_title()

    def _on_metadata_settings_change(self, _):
        # FIXME: not triggered.???
        self._update_title()

    def _update_title(self):
        label = self._get_label_from_metadata()
        self.title.value = f"<p>The standard label of psedopotential is: {label}</p>"

    def _get_label_from_metadata(self):
        metadata = self.metadata_settings.output_metadata

        try:
            element = metadata["element"]
            psp_type = metadata["type"]
            z_valence = metadata["z_valence"]
            family = metadata["family"]
            tool = metadata["tool"]
            version = metadata["version"]

            output_label = f"{element}.{psp_type}.{z_valence}.{tool}.{family}.{version}"
        except KeyError:
            # the metadata not set
            output_label = "Not set."

        return output_label

    def _update_state(self, _=None):
        if self.previous_step_state == self.State.SUCCESS:
            self.confirm_button.disabled = False
        elif self.previous_step_state == self.State.FAIL:
            self.state = self.State.FAIL
        else:
            self.state = self.State.INIT

    @traitlets.observe("previous_step_state")
    def _observe_previous_step_state(self, _):
        self._update_state()

    def confirm(self, _):
        for key in ["element", "type", "family", "z_valence", "tool", "version"]:
            if key not in self.metadata_settings.output_metadata:
                self.state = self.State.READY
                self._submission_blocker_messages.value = f"""
                    <div class="alert alert-info">
                    {key} is not set for labelling.</div>"""
        else:
            self._submission_blocker_messages.value = ""
            self.output_label = self._get_label_from_metadata()
            self.confirm_button.disabled = True
            self.state = self.State.SUCCESS

    @traitlets.default("state")
    def _default_state(self):
        return self.State.INIT


class ResourceSelectionWidget(ipw.VBox):
    """Widget for the selection of compute resources."""

    title = ipw.HTML(
        """<div style="padding-top: 0px; padding-bottom: 0px">
        <h4>Resources</h4>
    </div>"""
    )
    prompt = ipw.HTML(
        """<div style="line-height:120%; padding-top:0px">
        <p style="padding-bottom:10px">
        Specify the resources to use for the pw.x calculation.
        </p></div>"""
    )

    def __init__(self, **kwargs):
        extra = {
            "style": {"description_width": "150px"},
            "layout": {"min_width": "180px"},
        }
        self.num_nodes = ipw.BoundedIntText(
            value=1, step=1, min=1, max=1000, description="Nodes", **extra
        )
        self.num_cpus = ipw.BoundedIntText(
            value=1, step=1, min=1, description="CPUs", **extra
        )

        super().__init__(
            children=[
                self.title,
                ipw.HBox(
                    children=[self.prompt, self.num_nodes, self.num_cpus],
                    layout=ipw.Layout(justify_content="space-between"),
                ),
            ]
        )

    def reset(self):
        self.num_nodes.value = 1
        self.num_cpus.value = 1


class ParallelizationSettings(ipw.VBox):
    """Widget for setting the parallelization settings."""

    title = ipw.HTML(
        """<div style="padding-top: 0px; padding-bottom: 0px">
        <h4>Parallelization</h4>
    </div>"""
    )
    prompt = ipw.HTML(
        """<div style="line-height:120%; padding-top:0px">
        <p style="padding-bottom:10px">
        Specify the number of k-points pools for the calculations.
        </p></div>"""
    )

    def __init__(self, **kwargs):
        extra = {
            "style": {"description_width": "150px"},
            "layout": {"min_width": "180px"},
        }
        self.npools = ipw.BoundedIntText(
            value=1, step=1, min=1, max=128, description="Number of k-pools", **extra
        )
        super().__init__(
            children=[
                self.title,
                ipw.HBox(
                    children=[self.prompt, self.npools],
                    layout=ipw.Layout(justify_content="space-between"),
                ),
            ]
        )

    def reset(self):
        self.npools.value = 1


class SubmitSsspWorkChainStep(ipw.VBox, WizardAppWidgetStep):
    """step of submit verification"""

    pseudo = traitlets.Tuple(allow_none=True)
    value = traitlets.Unicode(allow_none=True)
    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    pseudo_label = traitlets.Unicode()
    workchain_settings = traitlets.Instance(WorkChainSettings, allow_none=True)

    _submission_blockers = traitlets.List(traitlets.Unicode)

    # Since for production it is now the only protocol
    _PROTOCOL = "acwf"

    codes_title = ipw.HTML(
        """<div style="padding-top: 0px; padding-bottom: 0px">
        <h4>Codes</h4></div>"""
    )
    codes_help = ipw.HTML(
        """<div style="line-height: 140%; padding-top: 0px; padding-bottom:
        10px"> Select the code to use for running the calculations. Please
        setup to run verification on the cluster with more than 16 cores.
        Otherwise the localhost resource will fully occupied and stuck. You can
        configure new ones on machines by clicking on
        "Setup new code".</div>"""
    )

    def __init__(self, **kwargs):
        self.pw_code = ComputationalResourcesWidget(
            description="pw.x:", input_plugin="quantumespresso.pw"
        )
        self.ph_code = ComputationalResourcesWidget(
            description="ph.x:",
            input_plugin="quantumespresso.ph",
        )

        self._submission_blocker_messages = ipw.HTML("")

        self.pw_code.observe(self._update_state, "value")
        self.pw_code.observe(self._update_resources, "value")

        self.ph_code.observe(self._update_state, "value")
        self.ph_code.observe(self._update_resources, "value")

        self.resources_config = ResourceSelectionWidget()
        self.parallelization = ParallelizationSettings()

        self.submit_button = ipw.Button(
            description="Submit",
            tooltip="Submit the calculation with the selected parameters.",
            icon="play",
            button_style="success",
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
            disabled=True,
        )

        self.submit_button.on_click(self._on_submit_button_clicked)

        # After all self variable set
        self.set_resource_defaults()

        super().__init__(
            children=[
                self.codes_title,
                self.codes_help,
                self.pw_code,
                self.ph_code,
                self.resources_config,
                self.parallelization,
                self._submission_blocker_messages,
                self.submit_button,
            ],
            **kwargs,
        )

    @traitlets.observe("state")
    def _observe_state(self, change):
        with self.hold_trait_notifications():
            self.disabled = change["new"] not in (
                self.State.READY,
                self.State.CONFIGURED,
            )
            self.submit_button.disabled = change["new"] != self.State.CONFIGURED

    def _update_resources(self, change):
        if change["new"] and (
            change["old"] is None
            or change["new"].computer.pk != change["old"].computer.pk
        ):
            self.set_resource_defaults(change["new"].computer)

    def set_resource_defaults(self, computer=None):

        if computer is None or computer.hostname == "localhost":
            self.resources_config.num_nodes.disabled = True
            self.resources_config.num_nodes.value = 1
            self.resources_config.num_cpus.max = os.cpu_count()
            self.resources_config.num_cpus.value = 1
            self.resources_config.num_cpus.description = "CPUs"
            self.parallelization.npools.value = 1
        else:
            default_mpiprocs = computer.get_default_mpiprocs_per_machine()
            self.resources_config.num_nodes.disabled = False
            self.resources_config.num_cpus.max = default_mpiprocs
            self.resources_config.num_cpus.value = default_mpiprocs
            self.resources_config.num_cpus.description = "CPUs/node"
            # self.parallelization.npools.value = self._get_default_parallelization()

        # self._check_resources()

    @traitlets.observe("_submission_blockers")
    def _observe_submission_blockers(self, change):
        if change["new"]:
            fmt_list = "\n".join((f"<li>{item}</li>" for item in sorted(change["new"])))
            self._submission_blocker_messages.value = f"""
                <div class="alert alert-info">
                <strong>The submission is blocked, due to the following reason(s):</strong>
                <ul>{fmt_list}</ul></div>"""
        else:
            self._submission_blocker_messages.value = ""

    def _toggle_install_widgets(self, change):
        if change["new"]:
            self.children = [
                child for child in self.children if child is not change["owner"]
            ]

    def _auto_select_code(self, change):
        if change["new"] and not change["old"]:
            for code in [
                "pw_code",
                "ph_code",
            ]:
                try:
                    code_widget = getattr(self, code)
                    code_widget.refresh()
                    code_widget.value = load_code(DEFAULT_PARAMETERS[code])
                except NotExistent:
                    pass

    def submit(self):
        """Run the workflow to calculate delta factor"""
        from aiida.engine import submit

        builder = VerificationWorkChain.get_builder()

        builder.pseudo = self.pseudo[1]
        builder.pw_code = self.pw_code.value
        builder.ph_code = self.ph_code.value
        builder.label = orm.Str(self.pseudo_label)

        builder.accuracy = {
            "protocol": orm.Str(self._PROTOCOL),
            "cutoff_control": orm.Str(self.workchain_settings.calc_type.value),
        }

        builder.convergence = {
            "protocol": orm.Str(self._PROTOCOL),
            "cutoff_control": orm.Str(self.workchain_settings.calc_type.value),
            "criteria": orm.Str(self.workchain_settings.criteria.value),
        }

        builder.properties_list = orm.List(list=self.workchain_settings.properties_list)

        builder.options = orm.Dict(
            dict={
                "resources": {
                    "num_machines": self.resources_config.num_nodes.value,
                    "num_mpiprocs_per_machine": self.resources_config.num_cpus.value,
                },
            }
        )
        builder.parallelization = orm.Dict(
            dict={"npool": self.parallelization.npools.value}
        )
        builder.clean_workchain = orm.Bool(True)  # anyway clean all

        # print("properties_list:", builder.properties_list.get_list())
        # print("protocol:", builder.accuracy.protocol.value)
        # print("criteria:", builder.convergence.criteria.value)
        # print("cutoff_control:", builder.accuracy.cutoff_control.value)
        # print("options:", builder.options.get_dict())
        # print("parallelization:", builder.parallelization.get_dict())
        # print("clean_workdir_level:", builder.clean_workchain.value)
        # print("label:", builder.label.value)

        process = submit(builder)
        process.description = self.pseudo_label

        self.value = process.uuid

    def _on_submit_button_clicked(self, _):
        self.submit_button.disabled = True
        self.submit()

        self.state = self.State.SUCCESS

    @traitlets.observe("pseudo")
    def _observe_pseudo(self, change):
        self._update_state()

    def _update_state(self, _=None):
        # Process is already running.
        if self.value is not None:
            self.state = self.State.SUCCESS

        # Input structure not specified.
        if not self.pseudo:
            self._submission_blockers = ["No pseudo selected."]
            # This blocker is handled differently than the other blockers,
            # because it is displayed as INIT state.
            self.state = self.State.INIT
        else:
            blockers = list(self._identify_submission_blockers())
            if any(blockers):
                self._submission_blockers = blockers
                self.state = self.State.READY
            else:
                self._submission_blockers = []
                self.state = self.state.CONFIGURED

    def _identify_submission_blockers(self):
        # No input pseudo specified.
        if self.pseudo is None:
            yield "No pseudo selected."

        # No code selected (this is ignored while the setup process is running).
        if self.pw_code.value is None:
            yield (
                'No pw.x code selected. Go to "Codes & '
                'Resources" to select a pw code.'
            )

        if self.ph_code.value is None:
            yield (
                'No ph.x code selected. Go to "Codes & '
                'Resources" to select a ph code.'
            )


class NodeViewWidget(ipw.VBox):

    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        self._output = ipw.Output()
        super().__init__(children=[self._output], **kwargs)

    @traitlets.observe("node")
    def _observe_node(self, change):
        if change["new"] != change["old"]:
            with self._output:
                clear_output(wait=True)
                if change["new"]:
                    display(viewer(change["new"]))


class ViewSsspAppWorkChainStatusAndResultsStep(ipw.VBox, WizardAppWidgetStep):

    value = traitlets.Unicode(allow_none=True)

    def __init__(self, **kwargs):
        self.process_tree = ProcessNodesTreeWidget()
        self.verification_status = ShowVerificationStatus()
        ipw.dlink((self, "value"), (self.process_tree, "value"))
        ipw.dlink((self, "value"), (self.verification_status, "value"))

        self.node_view = NodeViewWidget(layout={"width": "auto", "height": "auto"})
        ipw.dlink(
            (self.process_tree, "selected_nodes"),
            (self.node_view, "node"),
            transform=lambda nodes: nodes[0] if nodes else None,
        )
        self.process_status = ipw.VBox(children=[self.process_tree, self.node_view])

        # Setup process monitor
        self.process_monitor = ProcessMonitor(
            timeout=0.2,
            callbacks=[
                self.process_tree.update,
                self._update_state,
            ],
        )
        ipw.dlink((self, "value"), (self.process_monitor, "value"))

        super().__init__(
            [
                self.process_status,
                # self.verification_status,
            ],
            **kwargs,
        )

    def can_reset(self):
        "Do not allow reset while process is running."
        return self.state is not self.State.ACTIVE

    def reset(self):
        self.value = None

    def _update_state(self):
        if self.value is None:
            self.state = self.State.INIT
        else:
            process = load_node(self.value)
            process_state = process.process_state
            if process_state in (
                ProcessState.CREATED,
                ProcessState.RUNNING,
                ProcessState.WAITING,
            ):
                self.state = self.State.ACTIVE
            elif process_state in (ProcessState.EXCEPTED, ProcessState.KILLED):
                self.state = self.State.FAIL
            elif process_state is ProcessState.FINISHED:
                self.state = self.State.SUCCESS

    @traitlets.observe("value")
    def _observe_process(self, _):
        self._update_state()


def parse_state_to_info(process_state, exit_status=None) -> str:
    if process_state == "finished":
        if exit_status == 0:
            return "FINISH OKAY <span>&#10003;</span>"
        else:
            return f"FINISH FAILED[{exit_status}] <span>&#10060;</span>"

    if process_state == "waiting":
        return "RUNNING <span>&#9900;</span>"

    return "NOT RUNNING <span>&#9888;</span>"


class ShowVerificationStatus(ipw.VBox):

    value = traitlets.Unicode(allow_none=True)

    def __init__(self, **kwargs):
        init_info = parse_state_to_info(None)

        self.delta_measure_state = ipw.HTML(init_info)
        self.pressure_state = ipw.HTML(init_info)
        self.cohesive_energy_state = ipw.HTML(init_info)
        self.phonon_frequencies_state = ipw.HTML(init_info)
        self.bands_distance_state = ipw.HTML(init_info)

        status_delta_measure = ipw.HBox(
            children=[
                ipw.HTML("Delta factor:"),
                self.delta_measure_state,
            ]
        )
        status_conv_pressure = ipw.HBox(
            children=[
                ipw.HTML("Convergence: Pressure status:"),
                self.pressure_state,
            ]
        )
        status_conv_cohesive_energy = ipw.HBox(
            children=[
                ipw.HTML("Convergence - Cohesive energy:"),
                self.cohesive_energy_state,
            ]
        )
        status_conv_phonon = ipw.HBox(
            children=[
                ipw.HTML("Convergence - Phonon frequencies:"),
                self.phonon_frequencies_state,
            ]
        )
        status_conv_bands = ipw.HBox(
            children=[
                ipw.HTML("Convergence - Bands distance:"),
                self.bands_distance_state,
            ]
        )
        refresh_button = ipw.Button(
            description="Refresh",
            tooltip="Refresh the verification status",
        )
        refresh_button.on_click(self._on_refresh_button_clicked)

        super().__init__(
            children=[
                status_delta_measure,
                status_conv_cohesive_energy,
                status_conv_pressure,
                status_conv_phonon,
                status_conv_bands,
                refresh_button,
            ],
            **kwargs,
        )

    def _get_verification_info(self, process):
        """
        Go through the called workflow state and set the infos.
        """
        res = {}

        for sub in process.called:
            label = sub.attributes.get("process_label")
            process_state = sub.attributes.get("process_state")
            exit_status = sub.attributes.get("exit_status", None)

            info = parse_state_to_info(process_state, exit_status)

            if label == "DeltaFactorWorkChain":
                res["delta_measure"] = info

            if label == "ConvergencePressureWorkChain":
                res["convergence:pressure"] = info

            if label == "ConvergenceCohesiveEnergyWorkChain":
                res["convergence:cohesive_energy"] = info

            if label == "ConvergencePhononFrequenciesWorkChain":
                res["convergence:bands_distance"] = info

        return res

    def _update_state(self):
        if self.value is not None:
            process = load_node(self.value)
            infos = self._get_verification_info(process)
            not_running_text = parse_state_to_info(None)

            self.delta_measure_state.value = infos.get(
                "delta_measure", not_running_text
            )
            self.pressure_state.value = infos.get(
                "convergence:pressure", not_running_text
            )
            self.cohesive_energy_state.value = infos.get(
                "convergence:cohesive_energy", not_running_text
            )
            self.phonon_frequencies_state.value = infos.get(
                "convergence:phonon_frequencies", not_running_text
            )
            self.bands_distance_state.value = infos.get(
                "convergence:bands_distance", not_running_text
            )

    def _on_refresh_button_clicked(self, _):
        self._update_state()

    @traitlets.observe("value")
    def _observe_process(self, _):
        self._update_state()
