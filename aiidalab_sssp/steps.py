"""widget for pseudo inmport"""
import os
import io
from textwrap import indent

import ipywidgets as ipw
import traitlets
from IPython.display import display, clear_output

from aiida import orm
from aiida.plugins import DataFactory, WorkflowFactory
from aiida.engine import submit, ProcessState
from aiida.orm import ProcessNode, Node, load_code
from aiida.common import NotExistent

from aiida_sssp_workflow.utils import helper_parse_upf
from aiida_sssp_workflow.workflows.verifications import DEFAULT_PROPERTIES_LIST

from aiidalab_sssp.parameters import DEFAULT_PARAMETERS
from aiidalab_sssp.setup_codes import QESetupWidget

from aiidalab_widgets_base import (
    CodeDropdown,
    ProcessMonitor,
    ProcessNodesTreeWidget,
    WizardAppWidgetStep,
    viewer,
    ComputationalResourcesWidget,
)

UpfData = DataFactory('pseudo.upf')
VerificationWorkChain = WorkflowFactory('sssp_workflow.verification')

class PseudoUploadWidget(ipw.VBox):
    """Class that allows to upload pseudopotential from user's computer."""
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    message = traitlets.Unicode()

    pseudo_filename: str

    def __init__(self, title='', description="Upload Pseudopotential"):
        self.title = title
        self.file_upload = ipw.FileUpload(description=description,
                                          multiple=False,
                                          layout={'width': 'initial'})
        supported_formats = ipw.HTML(
            """<a href="http://www.quantum-espresso.org/pseudopotentials/
unified-pseudopotential-format" target="_blank">
Supported pseudo formats (Now only support UPF type)
</a>""")
        self.file_upload.observe(self._on_file_upload, names='value')
        self.message = ''
        super().__init__(children=[self.file_upload, supported_formats])

    def _on_file_upload(self, change=None):
        """When file upload button is pressed."""
        fname, item = next(iter(change['new'].items()))
        try:
            content = item['content']

            # Order matters make sure when pseudo change 
            # the pseudo_filename is set 
            self.pseudo_filename = fname
            self.pseudo = UpfData(io.BytesIO(content))
        except ValueError:
            self.message = 'wrong pseudopotential file type. (Only UPF support now)'

class PseudoSelectionStep(ipw.VBox, WizardAppWidgetStep):
    """
    Upload a pesudopotential and store it as UpfData in database
    """
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    confirmed_pseudo = traitlets.Instance(UpfData, allow_none=True)

    def __init__(self, **kwargs):
        self.pseudo_upload = PseudoUploadWidget()
        self.pseudo_upload.observe(self._observe_pseudo_upload, 'pseudo')

        self.description = ipw.HTML("""
            <p>Select a pseudopotential from one of the following sources and then
            click "Confirm" to go to the next step.</p><i class="fa fa-exclamation-circle"
            aria-hidden="true"></i> Currently only UPF pseudopotential file are
            supported.
            """
        )

        self.pseudo_text = ipw.Text(
            placeholder='[No pseudo selected]',
            description='Selected:',
            disabled=True,
            layout=ipw.Layout(width='auto'),
        )

        self.confirm_button = ipw.Button(
            description='Confirm',
            tooltip=
            "Confirm the currently selected pseudopotential and go to the next step.",
            button_style='success',
            icon='check-circle',
            disabled=True,
            layout=ipw.Layout(width='auto'),
        )
        self.confirm_button.on_click(self.confirm)
        self.message_area = ipw.HTML()

        super().__init__(
            children=[
                self.description, 
                self.pseudo_upload, 
                self.pseudo_text,
                self.message_area,
                self.confirm_button
            ],
            **kwargs
        )
                         
    @traitlets.default('state')
    def _default_state(self):
        return self.State.INIT

    def _update_state(self):
        if self.pseudo is None:
            self.state = self.State.READY
        else:
            if self.confirmed_pseudo is None:
                self.state = self.State.CONFIGURED
                self.confirm_button.disabled = False
            else:
                self.state = self.State.SUCCESS
                self.confirm_button.disabled = True

    def _observe_pseudo_upload(self, _):
        with self.hold_trait_notifications():
            if self.pseudo_upload.pseudo is None:
                self.message_area.value = self.pseudo_upload.message
            else:
                # Upload then set pseudo and show filename on text board
                self.pseudo_text.value = self.pseudo_upload.pseudo_filename
                self.pseudo = self.pseudo_upload.pseudo

                if self.pseudo_upload.message:
                    self.message_area.value = self.pseudo_upload.message

            self._update_state()

    @traitlets.observe('confirmed_pseudo')
    def _observe_confirmed_structure(self, _):
        with self.hold_trait_notifications():
            self._update_state()

    def can_reset(self):
        return self.confirmed_pseudo is not None

    def confirm(self, _=None):
        self.confirmed_pseudo = self.pseudo

        self._update_state()

    def reset(self):  # unconfirm
        self.confirmed_pseudo = None

        self._update_state()


class WorkChainSettings(ipw.VBox):

    protocol_help = ipw.HTML(
        """<div style="line-height: 140%; padding-top: 6px; padding-bottom: 0px">
        The calculation protocol setup the parameters used for pseudopotential 
        verification. The criteria protocol determine when the wavefunction and 
        charge density cutoff tests are converged.
        The "THEOS" calculation protocol represents a set of parameters compatible 
        with aiida-common-workflow.
        Choose the "efficiency" protocol for cutoff test to give a efficiency 
        pseudopotential. The "precision" protocol that provides more
        accuracy pseudopotential but will take longer.</div>"""
    )
    properties_list = traitlets.List()

    def __init__(self, **kwargs):

        self.delta_run = ipw.Checkbox(
            description="",
            tooltip="Calculate the delta measure w.r.t AE.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.conv_cohesive_run = ipw.Checkbox(
            description="",
            tooltip="Convergence test on cohesive energy.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.conv_pressure_run = ipw.Checkbox(
            description="",
            tooltip="Convergence test on pressue.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )
        self.conv_phonon_run = ipw.Checkbox(
            description="",
            tooltip="Convergence test on phonon.",
            indent=False,
            value=True,
            layout=ipw.Layout(max_width="10%"),
        )

        self.delta_run.observe(self._update_properties_list, 'value')
        self.conv_cohesive_run.observe(self._update_properties_list, 'value')
        self.conv_pressure_run.observe(self._update_properties_list, 'value')
        self.conv_phonon_run.observe(self._update_properties_list, 'value')

        self.properties_list = DEFAULT_PROPERTIES_LIST

        # Work chain protocol
        self.protocol_calculation = ipw.ToggleButtons(
            options=["theos", "test"],
            value="test",
        )

        self.protocol_criteria = ipw.ToggleButtons(
            options=["efficiency", "precision"],
            value="efficiency",
        )

        super().__init__(
            children=[
                ipw.HTML("Select which properties to verified:"),
                ipw.HBox(children=[ipw.HTML("<b>Delta measure</b>"), self.delta_run]),
                ipw.HBox(children=[ipw.HTML("<b>Convergence: cohesive energy</b>"), self.conv_cohesive_run]),
                ipw.HBox(children=[ipw.HTML("<b>Convergence: phonon frequencies</b>"), self.conv_phonon_run]),
                ipw.HBox(children=[ipw.HTML("<b>Convergence: pressure</b>"), self.conv_pressure_run]),
                ipw.HTML("Select the calculation protocol:", layout=ipw.Layout(flex="1 1 auto")),
                self.protocol_calculation,
                ipw.HTML("Select the criteria protocol:", layout=ipw.Layout(flex="1 1 auto")),
                self.protocol_criteria,
                self.protocol_help,
            ],
            **kwargs,
        )

    def _update_properties_list(self, _):
        lst = []
        if self.delta_run.value:
            lst.append('delta_factor')

        if self.conv_cohesive_run.value:
            lst.append('convergence:cohesive_energy')

        if self.conv_phonon_run.value:
            lst.append('convergence:phonon_frequencies')

        if self.conv_pressure_run.value:
            lst.append('convergence:pressure')

        self.properties_list = lst

class ConfigureSsspWorkChainStep(ipw.VBox, WizardAppWidgetStep):

    confirmed = traitlets.Bool()
    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    workchain_settings = traitlets.Instance(WorkChainSettings, allow_none=True)

    def __init__(self, **kwargs):
        self.workchain_settings = WorkChainSettings()
        self.workchain_settings.delta_run.observe(self._update_state, "value")
        self.workchain_settings.conv_cohesive_run.observe(self._update_state, "value")

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
            self.workchain_settings.delta_run.value = parameters['run_delta']
            self.workchain_settings.conv_cohesive_run.value = parameters['run_conv_cohesive']
            self.workchain_settings.protocol_calculation.value = parameters['calc_protocol']
            self.workchain_settings.protocol_criteria.value = parameters['cri_protocol']

    def _update_state(self, _=None):
        if self.previous_step_state == self.State.SUCCESS:
            self.confirm_button.disabled = False
            if not (
                self.workchain_settings.delta_run.value
                or self.workchain_settings.conv_cohesive_run.value
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
        <element>/<psp_type>/<psp_family>/<psp_version>/<psp_extra_label> 

    In the future this should be a formatted class of data that can be used
    to identify the pseudopotentials.
    """

    def __init__(self, **kwargs):
        extra = {
            "style": {"description_width": "180px"},
            "layout": {"min_width": "310px"},
        }

        self.psp_family = ipw.Text(
            placeholder='Unresolved',
            description='Pseudopotential type:',
            **extra,
        )
        self.psp_version= ipw.Text(
            placeholder='Unresolved',
            description='Pseudopotential version:',
            **extra,
        )
        self.psp_extra_label = ipw.Text(
            placeholder='Optional',
            description='Pseudopotential extra label:',
            **extra,
        )

        self.description = ipw.Textarea(
            placeholder='Optional',
            description='Description:',
            **extra,
        )

        super().__init__(
            children=[
                self.psp_family,
                self.psp_version,
                self.psp_extra_label,
                self.description,
            ],
            **kwargs,
        )

class SettingPseudoMetadataStep(ipw.VBox, WizardAppWidgetStep):
    """setting the extra metadata for the future query and description display of the pseudo
    """

    pseudo = traitlets.Instance(UpfData, allow_none=True)
    confirmed = traitlets.Bool()
    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    metadata_settings = traitlets.Instance(MetadataSettings, allowed_none=True)

    metadata_help = ipw.HTML("""<div style="line-height:120%; padding-top:10px;">
        <p>There is no general rule of thumb on how to name the extra metadata. </p>
        <p>The family and version field deduct from input pseudopotential.</p>
        <p>In general:</p>
        <ul>
        <li>family indicate the library, sg15, gbrv etc.</li>
        <li>version of library.</li>
        <li>extra label is optional append to the label.</li>
        <li>description of node.</li>
        </ul>
        </div>""")

    def __init__(self, **kwargs):
        self.metadata_settings = MetadataSettings()
        self._psp_element = None
        self._psp_type = None

        self.title = ipw.HTML("<p>No pseudopotential detect</p>")
        
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

    @traitlets.observe("pseudo")
    def _observe_pseudo(self, _):
        if self.pseudo:
            header = helper_parse_upf(self.pseudo)
            self._psp_type = header.get('pseudo_type', None)
            self._psp_element =  self.pseudo.element

            self.title.value = f"<p>Element: {self._psp_element}, Type: {self._psp_type}</p>"

    def confirm(self, _None):
        if not (
            self.metadata_settings.psp_family.value
            and self.metadata_settings.psp_version.value
            and self._psp_element
            and self._psp_type
        ):
            self.state = self.State.READY
            self._submission_blocker_messages.value = """
                <div class="alert alert-info">
                Not fully set.</div>"""
        else:
            self._submission_blocker_messages.value = ""
            self.confirm_button.disabled = True
            self.state = self.State.SUCCESS

    @traitlets.default("state")
    def _default_state(self):
        return self.State.INIT

    def reset(self):
        self.title.value = ""


class NodeViewWidget(ipw.VBox):

    node = traitlets.Instance(Node, allow_none=True)

    def __init__(self, **kwargs):
        self._output = ipw.Output()
        super().__init__(children=[self._output], **kwargs)

    @traitlets.observe("node")
    def _observe_node(self, change):
        if change["new"] != change["old"]:
            with self._output:
                clear_output()
                if change["new"]:
                    display(viewer(change["new"]))

class ViewSsspAppWorkChainStatusAndResultsStep(ipw.VBox, WizardAppWidgetStep):

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.process_tree = ProcessNodesTreeWidget()
        self.verification_status = ShowVerificationStatus()
        ipw.dlink((self, "process"), (self.process_tree, "process"))
        ipw.dlink((self, "process"), (self.verification_status, "process"))

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
        ipw.dlink((self, "process"), (self.process_monitor, "process"))

        super().__init__([
            self.process_status,
            self.verification_status,
        ], **kwargs)

    def can_reset(self):
        "Do not allow reset while process is running."
        return self.state is not self.State.ACTIVE

    def reset(self):
        self.process = None

    def _update_state(self):
        if self.process is None:
            self.state = self.State.INIT
        else:
            process_state = self.process.process_state
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

    @traitlets.observe("process")
    def _observe_process(self, change):
        self._update_state()

class CodeSettings(ipw.VBox):

    codes_title = ipw.HTML(
        """<div style="padding-top: 0px; padding-bottom: 0px">
        <h4>Codes</h4></div>"""
    )
    codes_help = ipw.HTML(
        """<div style="line-height: 140%; padding-top: 0px; padding-bottom:
        10px"> Select the code to use for running the calculations. The codes
        on the local machine (localhost) are installed by default, but you can
        configure new ones on potentially more powerful machines by clicking on
        "Setup new code".</div>"""
    )

    def __init__(self, **kwargs):

        self.pw = CodeDropdown(
            input_plugin="quantumespresso.pw",
            description="pw.x:",
            setup_code_params={
                "computer": "localhost",
                "description": "pw.x in AiiDAlab container.",
                "label": "pw",
                "input_plugin": "quantumespresso.pw",
                "remote_abs_path": "/usr/bin/pw.x",
            },
        )
        self.ph = CodeDropdown(
            input_plugin="quantumespresso.ph",
            description="ph.x:",
            setup_code_params={
                "computer": "localhost",
                "description": "ph.x in AiiDAlab container.",
                "label": "ph",
                "input_plugin": "quantumespresso.ph",
                "remote_abs_path": "/usr/bin/ph.x",
            },
        )
        super().__init__(
            children=[
                self.codes_title,
                self.codes_help,
                self.pw,
                self.ph,
            ],
            **kwargs,
        )

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

    process = traitlets.Instance(ProcessNode, allow_none=True)
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    previous_step_state = traitlets.UseEnum(WizardAppWidgetStep.State)
    metadata_settings = traitlets.Instance(MetadataSettings, allow_none=True)
    workchain_settings = traitlets.Instance(WorkChainSettings, allow_none=True)

    _submission_blockers = traitlets.List(traitlets.Unicode)

    codes_title = ipw.HTML(
        """<div style="padding-top: 0px; padding-bottom: 0px">
        <h4>Codes</h4></div>"""
    )
    codes_help = ipw.HTML(
        """<div style="line-height: 140%; padding-top: 0px; padding-bottom:
        10px"> Select the code to use for running the calculations. The codes
        on the local machine (localhost) are installed by default, but you can
        configure new ones on potentially more powerful machines by clicking on
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
        self.ph_code.observe(self._update_state, "value")

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

        # The QE setup widget checks whether there are codes that match specific
        # expected labels (e.g. "pw-6.7@localhost") and triggers both the
        # installation of QE into a dedicated conda environment and the setup of
        # the codes in case that they are not already configured.
        self.qe_setup_status = QESetupWidget()
        self.qe_setup_status.observe(self._update_state, "busy")
        self.qe_setup_status.observe(self._toggle_install_widgets, "installed")
        self.qe_setup_status.observe(self._auto_select_code, "installed")

        # After all self variable set
        self.set_selected_codes(DEFAULT_PARAMETERS)
        self.set_resource_defaults()

        super().__init__(
            children=[
                self.codes_title,
                self.codes_help, 
                self.pw_code,
                self.ph_code,
                self.resources_config,
                self.parallelization,
                self.qe_setup_status,
                self._submission_blocker_messages, 
                self.submit_button,
            ], 
            **kwargs
        )

    @traitlets.observe("state")
    def _observe_state(self, change):
        with self.hold_trait_notifications():
            self.disabled = change["new"] not in (
                self.State.READY,
                self.State.CONFIGURED,
            )
            self.submit_button.disabled = change["new"] != self.State.CONFIGURED

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
            self.parallelization.npools.value = self._get_default_parallelization()

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

    def set_selected_codes(self, parameters):
        """Set the inputs in the GUI based on a set of parameters."""

        # Codes
        def _load_code(code):
            if code is not None:
                try:
                    return load_code(code)
                except NotExistent:
                    return None

        with self.hold_trait_notifications():
            # Codes
            self.pw_code.value = _load_code(parameters["pw_code"])
            self.ph_code.value = _load_code(parameters["ph_code"])

    def submit(self):
        """Run the workflow to calculate delta factor"""
        builder = VerificationWorkChain.get_builder()

        builder.pseudo = self.pseudo
        builder.pw_code = self.pw_code.value
        builder.ph_code = self.ph_code.value

        builder.protocol_calculation = orm.Str(self.workchain_settings.protocol_calculation.value)
        builder.protocol_criteria = orm.Str(self.workchain_settings.protocol_criteria.value)
        builder.properties_list = orm.List(list=self.workchain_settings.properties_list)

        builder.options = orm.Dict(dict={
            'resources': {
                "num_machines": self.resources_config.num_nodes.value,
                "num_mpiprocs_per_machine": self.resources_config.num_cpus.value,
            },
        })
        builder.parallelization = orm.Dict(dict={"npool": self.parallelization.npools.value})
        builder.clean_workdir_level = orm.Int(9) # anyway clean all

        self.process = submit(builder)

        # set extras for easy query and comprehensive show results
        header = helper_parse_upf(self.pseudo)

        element = self.pseudo.element
        psp_type = header.get('pseudo_type', None)
        psp_family = self.metadata_settings.psp_family.value,
        psp_version = self.metadata_settings.psp_version.value,
        psp_extra_label = self.metadata_settings.psp_extra_label.value,
        extras = {
            'element': element,
            'psp_type': psp_type,
            'psp_family': psp_family,
            'psp_version': psp_version,
        }
        label = f'{element}/z={self.pseudo.z_valence}/{psp_type}/{psp_family}/{psp_version}'

        if psp_extra_label:
            label += f'/{psp_extra_label}'

        extras['psp_label'] = label
        self.process.set_extra_many(extras)

        self.process.description = self.metadata_settings.description

    def _on_submit_button_clicked(self, _):
        self.submit_button.disabled = True
        self.submit()

    # @traitlets.observe('process')
    # def _observe_process(self, change):
    #     with self.hold_trait_notifications():
    #         process_node = change['new']
    #         if process_node is not None:
    #             self.pseudo = process_node.inputs.pseudo
    #             # TODO: I can do builder parameters setting here
    #         self._update_state()

    @traitlets.observe("pseudo")
    def _observe_pseudo(self, change):
        self._update_state()

    def _update_state(self, _=None):
        # Process is already running.
        if self.process is not None:
            self.state = self.State.SUCCESS

        # Input structure not specified.
        if self.pseudo is None:
            self._submission_blockers = ["No pseudo selected."]
            # This blocker is handled differently than the other blockers,
            # because it is displayed as INIT state.
            self.state = self.State.INIT

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
        if (
            self.pw_code.value is None
        ):
            yield (
                'No pw.x code selected. Go to "Codes & '
                'Resources" to select a pw code.'
            )

        if (
            self.ph_code.value is None
        ):
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
                clear_output()
                if change["new"]:
                    display(viewer(change["new"]))

class ViewSsspAppWorkChainStatusAndResultsStep(ipw.VBox, WizardAppWidgetStep):

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        self.process_tree = ProcessNodesTreeWidget()
        self.verification_status = ShowVerificationStatus()
        ipw.dlink((self, "process"), (self.process_tree, "process"))
        ipw.dlink((self, "process"), (self.verification_status, "process"))

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
        ipw.dlink((self, "process"), (self.process_monitor, "process"))

        super().__init__([
            self.process_status,
            self.verification_status,
        ], **kwargs)

    def can_reset(self):
        "Do not allow reset while process is running."
        return self.state is not self.State.ACTIVE

    def reset(self):
        self.process = None

    def _update_state(self):
        if self.process is None:
            self.state = self.State.INIT
        else:
            process_state = self.process.process_state
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

    @traitlets.observe("process")
    def _observe_process(self, change):
        self._update_state()


def parse_state_to_info(process_state, exit_status=None) -> str:
    if process_state == 'finished':
        if exit_status == 0:
            return 'FINISH OKAY <span>&#10003;</span>'
        else:
            return f'FINISH FAILED[{exit_status}] <span>&#10060;</span>'

    if process_state == 'waiting':
        return 'RUNNING <span>&#9900;</span>'

    return 'NOT RUNNING <span>&#9888;</span>'

class ShowVerificationStatus(ipw.VBox):

    process = traitlets.Instance(ProcessNode, allow_none=True)

    def __init__(self, **kwargs):
        init_info = parse_state_to_info(None)

        self.delta_factor_state = ipw.HTML(init_info)
        self.pressure_state = ipw.HTML(init_info)
        self.cohesive_energy_state = ipw.HTML(init_info)
        self.phonon_frequencies_state = ipw.HTML(init_info)
        self.bands_distance_state = ipw.HTML(init_info)

        status_delta_factor = ipw.HBox(
            children=[
                ipw.HTML('Delta factor:'),
                self.delta_factor_state,
            ]
        )
        status_conv_pressure = ipw.HBox(
            children=[
                ipw.HTML('Convergence: Pressure status:'),
                self.pressure_state,
            ]
        )
        status_conv_cohesive_energy= ipw.HBox(
            children=[
                ipw.HTML('Convergence - Cohesive energy:'),
                self.cohesive_energy_state,
            ]
        )
        status_conv_phonon = ipw.HBox(
            children=[
                ipw.HTML('Convergence - Phonon frequencies:'),
                self.phonon_frequencies_state,
            ]
        )
        status_conv_bands = ipw.HBox(
            children=[
                ipw.HTML('Convergence - Bands distance:'),
                self.bands_distance_state,
            ]
        )
        refresh_button = ipw.Button(
            description='Refresh',
            tooltip='Refresh the verification status',
        )
        refresh_button.on_click(self._on_refresh_button_clicked)

        super().__init__(
            children=[
                status_delta_factor,
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
            label = sub.attributes.get('process_label')
            process_state = sub.attributes.get('process_state')
            exit_status = sub.attributes.get('exit_status', None)

            info = parse_state_to_info(process_state, exit_status)

            if  label == 'DeltaFactorWorkChain':
                res['delta_factor'] = info

            if label == 'ConvergencePressureWorkChain':
                res['convergence:pressure'] = info

            if label == 'ConvergenceCohesiveEnergyWorkChain':
                res['convergence:cohesive_energy'] = info

            if label == 'ConvergencePhononFrequenciesWorkChain':
                res['convergence:bands_distance'] = info

        return res

    def _update_state(self):
        if self.process is not None:
            infos = self._get_verification_info(self.process)
            not_running_text = parse_state_to_info(None)

            self.delta_factor_state.value = infos.get('delta_factor', not_running_text)
            self.pressure_state.value = infos.get('convergence:pressure', not_running_text)
            self.cohesive_energy_state.value = infos.get('convergence:cohesive_energy', not_running_text)
            self.phonon_frequencies_state.value = infos.get('convergence:phonon_frequencies', not_running_text)
            self.bands_distance_state.value = infos.get('convergence:bands_distance', not_running_text)

    def _on_refresh_button_clicked(self, _):
        self._update_state()

    @traitlets.observe('process')
    def _observe_process(self, change):
        self._update_state()