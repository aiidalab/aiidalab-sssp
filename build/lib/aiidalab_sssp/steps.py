"""widget for pseudo inmport"""
import os
import io

import ipywidgets as ipw
import traitlets
from IPython.display import clear_output

from aiida import orm
from aiida.plugins import DataFactory, WorkflowFactory
from aiida.engine import submit, ProcessState
from aiida.orm import ProcessNode, Node

from aiida_sssp_workflow.utils import helper_parse_upf

from aiidalab_widgets_base import (
    CodeDropdown,
    ProcessMonitor,
    ProcessNodesTreeWidget,
    WizardAppWidgetStep,
    viewer
)

UpfData = DataFactory('pseudo.upf')
VerificationWorkChain = WorkflowFactory('sssp_workflow.verification')

class PseudoInputStep(ipw.VBox, WizardAppWidgetStep):
    """
    Upload a pesudopotential and store it as UpfData in database
    """
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    pseudo_filename = traitlets.Unicode(allow_none=False)
    confirmed_pseudo = traitlets.Instance(UpfData, allow_none=True)

    def __init__(self, description=None, **kwargs):
        self.pseudo_upload_widget = PseudoUploadWidget()
        if description is None:
            description = ipw.Label(
                'Select a pseudopotential from one of the following sources and then '
                'click "Confirm" to go to the next step.')
        self.description = description

        self.pseudo_name_text = ipw.Text(
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

        # Create directional link from the (read-only) 'pseudo_node' traitlet of the
        # pseudo upload widget to our 'pseudo' traitlet:
        ipw.dlink((self.pseudo_upload_widget, 'pseudo'), (self, 'pseudo'))
        ipw.dlink((self.pseudo_upload_widget, 'pseudo_filename'),
                  (self, 'pseudo_filename'))

        super().__init__(children=[
            self.description, self.pseudo_upload_widget, self.pseudo_name_text,
            self.confirm_button
        ],
        **kwargs)
                         
    @traitlets.default('state')
    def _default_state(self):
        return self.State.INIT

    def _update_state(self):
        if self.pseudo is None:
            if self.confirmed_pseudo is None:
                self.state = self.State.READY
            else:
                self.state = self.State.SUCCESS
        else:
            if self.confirmed_pseudo is None:
                self.state = self.State.CONFIGURED
            else:
                self.state = self.State.SUCCESS

    @traitlets.observe('pseudo_filename')
    def _observe_pseudo_filename(self, change):
        pseudo_filename = change['new']
        with self.hold_trait_notifications():
            self.pseudo_name_text.value = pseudo_filename.split('.')[0]

    @traitlets.observe('pseudo')
    def _observe_pseudo(self, change):
        # the first time set the pseudo
        if self.pseudo:
            self.confirm_button.disabled = False

        # after set the new pseudo
        if self.pseudo != change['new']:
            self.confirm_button.disabled = False

    @traitlets.observe('confirmed_pseudo')
    def _observe_confirmed_structure(self, _):
        with self.hold_trait_notifications():
            self._update_state()

    @traitlets.observe('state')
    def _observe_state(self, change):
        with self.hold_trait_notifications():
            state = change['new']
            self.confirm_button.disabled = state != self.State.CONFIGURED

    def confirm(self, _=None):
        self.confirmed_pseudo = self.pseudo
        self.confirm_button.disabled = True 

    def reset(self):  # unconfirm
        self.confirmed_structure = None


class PseudoUploadWidget(ipw.VBox):
    """Class that allows to upload pseudopotential from user's computer."""
    pseudo = traitlets.Instance(UpfData, allow_none=True)
    pseudo_filename = traitlets.Unicode(allow_none=False)

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
        super().__init__(children=[self.file_upload, supported_formats])

    def _on_file_upload(self, change=None):
        """When file upload button is pressed."""
        fname, item = next(iter(change['new'].items()))
        try:
            content = item['content']
            self.pseudo = UpfData(io.BytesIO(content))
            self.pseudo_filename = fname
        except ValueError:
            print('wrong pseudopotential file type. (Only UPF support now)')

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
        ipw.dlink((self, "process"), (self.process_tree, "process"))

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

        super().__init__([self.process_status], **kwargs)

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
        Specify the number of MPI tasks for this calculation.
        In general, larger structures will require a larger number of tasks.
        </p></div>"""
    )

    def __init__(self, **kwargs):
        extra = {
            "style": {"description_width": "150px"},
            # "layout": {"max_width": "200px"},
            "layout": {"min_width": "310px"},
        }

        self.num_mpi_tasks = ipw.BoundedIntText(
            value=1, step=1, min=1, description="# MPI tasks", **extra
        )

        super().__init__(
            children=[
                self.title,
                ipw.HBox(children=[self.prompt, self.num_mpi_tasks]),
            ]
        )

    def reset(self):
        self.num_mpi_tasks.value = 1

class SubmitVerificationStep(ipw.VBox, WizardAppWidgetStep):
    """step of submit verification"""

    process = traitlets.Instance(ProcessNode, allow_none=True)
    input_pseudo = traitlets.Instance(UpfData, allow_none=True)

    _submission_blockers = traitlets.List(traitlets.Unicode)

    skip = False

    def __init__(self, **kwargs):
        self.pw_code = CodeDropdown(input_plugin='quantumespresso.pw',
                               description="PW code")
        self.ph_code = CodeDropdown(input_plugin='quantumespresso.ph',
                               description="PH code")

        self.pw_code.observe(self._update_state, "selected_code")
        self.ph_code.observe(self._update_state, "selected_code")

        self.code_group = ipw.VBox(children=[self.pw_code, self.ph_code])

        protocol_list = ['efficiency', 'precision', 'test'] # will read from sssp plugin

        # properties checkbox setting      

        # aiida_sssp_workflow.workflows.verifications::DEFAULT_PROPERTIES_LIST  
        self.properties_list = [
            'delta_factor', 
            'convergence:cohesive_energy', 
            'convergence:phonon_frequencies',
            'convergence:pressure']

        option_checkbox_extra = {
            'style': {
                'description_width': 'initial'
            },
        }

        delta_factor_checkbox = ipw.Checkbox(value=True, description='Delta Factor (the difference of EOS to wien2K)', **option_checkbox_extra)
        delta_factor_checkbox.observe(self._on_delta_factor_checkbox_change, names="value")

        cohesive_energy_checkbox = ipw.Checkbox(value=True, description='Convergence: Cohesive energy', **option_checkbox_extra)
        cohesive_energy_checkbox.observe(self._on_cohesive_energy_checkbox_change, names="value")

        phonon_checkbox = ipw.Checkbox(value=True, description='Convergence: Phonon Frequencies', **option_checkbox_extra)
        phonon_checkbox.observe(self._on_phonon_frequencies_checkbox_change, names="value")

        pressure_checkbox = ipw.Checkbox(value=True, description='Convergence: Pressure', **option_checkbox_extra)
        pressure_checkbox.observe(self._on_pressure_checkbox_change, names="value")

        option_box_extra = {
            'style': {
                'description_width': 'initial'
            },
        }

        self.protocol = ipw.ToggleButtons(
            options=protocol_list,
            value='efficiency')

        self.dual= ipw.BoundedIntText(
            value=8,
            step=1,
            min=1,
            description="# dual (ecutrho/ecutwfc)",
            **option_box_extra)

        self.query_pp_element = ipw.Text(
            value='Undetected',
            placeholder='The element of the pseudo',
            description='Element:',
            disabled=True
        )
        self.query_pp_type = ipw.Text(
            value='Undetected',
            placeholder='The type of the pseudo',
            description='PP type:',
            disabled=True
        )
        self.query_pp_family = ipw.Text(
            value='Unset',
            placeholder='The family name of the pseudo',
            description='Family name:',
            disabled=False
        )
        self.query_pp_version = ipw.Text(
            value='Unset',
            placeholder='The version number of the pseudo',
            description='Version:',
            disabled=False
        )
        self.extra_label = ipw.Text(
            value='Unset',
            placeholder='The label of the pseudo',
            description='Label:',
            disabled=False
        )
        self.extra_description = ipw.Text(
            value='Unset',
            placeholder='The description of the pseudo',
            description='Description:',
            disabled=False
        )
        # the settings for protocol choose (dropdown) and properties (checkboxes) and infos for query

        propertis_prompt = ipw.HTML(
            """
            <p>Choose the properties you want to verify for the pseudopotential.</p>
            <p>All the calculations are performed on the ground-state structures of
            elemental crystals at 0K. </p>
            <p>For the detailed logic of how cohesive energy, phonon frequencies and pressure properties are
            evaluated, please check .. for reference.</p>
            """
        )
        protocol_prompt = ipw.HTML(
            "The protocol predefine calculation parameters for the calculation."
        )
        dual_prompt = ipw.HTML(
            "The dual will influence the ecutrho for each ecutwfc setting in convergence verification."
        )

        properties_setting = ipw.VBox(
            children=[
                propertis_prompt,
                delta_factor_checkbox, 
                cohesive_energy_checkbox, 
                phonon_checkbox, 
                pressure_checkbox,
            ],
        )
        self.settings = ipw.VBox(
            children=[
                protocol_prompt,
                self.protocol,
                dual_prompt,
                self.dual,
                properties_setting,
            ]
        )

        # setting the extra metadata for the future query and description display of the pseudo

        extra_metadata_prompt = ipw.HTML(
            "Set metadata for the pseudopotential verification process.")
        extra_metadata_help = ipw.HTML("""<div style="line-height:120%; padding-top:25px;">
            <p>There is no general rule of thumb on how to name the extra metadata. In general:</p>
            <ul>
            <li>Element and PP type are read from the uploaded pseudopotential file and not setable.</li>
            <li>Family name indicate the library of the pseudopotential, such as sg15, gbrv etc.</li>
            <li>Family Version is the version of pseudopotential in this pp family.</li>
            <li>Label is the abbrevation to represent the pseudopotential in DB and in inspect step.</li>
            <li>Description is the description and comment info for the pseudopotential and for this verification process.</li>
            </ul>
            <p>However, it is not apparent to set every options.</p></div>""")

        self.set_extra_metadata = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    extra_metadata_prompt,
                    self.query_pp_element,
                    self.query_pp_type,
                    self.query_pp_family,
                    self.query_pp_version,
                    self.extra_label,
                    self.extra_description,
                ],
            ),
            extra_metadata_help,
        ])

        self.number_of_nodes = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# nodes",
            disabled=False,
            **option_box_extra)
        self.cpus_per_node = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# cpus per node",
            **option_box_extra)
        self.total_num_cpus = ipw.BoundedIntText(
            value=1, step=1, min=1,
            description="# total cpus",
            disabled=True,
            **option_box_extra)

        # Update the total # of CPUs int text:
        self.number_of_nodes.observe(self._update_total_num_cpus, 'value')
        self.cpus_per_node.observe(self._update_total_num_cpus, 'value')

        resource_selection_prompt = ipw.HTML(
            "Select the compute resources for this calculation.")
        resource_selection_help = ipw.HTML("""<div style="line-height:120%; padding-top:25px;">
            <p>There is no general rule of thumb on how to select the appropriate number of
            nodes and cores. In general:</p>
            <ul>
            <li>Increase the number of nodes if you run out of memory for larger structures.</li>
            <li>Increase the number of nodes and cores if you want to reduce the total runtime.</li>
            </ul>
            <p>However, specifying the optimal configuration of resources is a complex issue and
            simply increasing either cores or nodes may not have the desired effect.</p></div>""")
        self.resources = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    resource_selection_prompt,
                    self.number_of_nodes,
                    self.cpus_per_node,
                    self.total_num_cpus,
                ],
                layout=ipw.Layout(min_width='310px'),
            ),
            resource_selection_help,
        ])


        # Clicking on the 'verify' button will trigger the execution of the
        # verify() method.
        self.verify_button = ipw.Button(
            description='Verify',
            tooltip="Submit the calculation with the selected parameters.",
            icon='play',
            button_style='success',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=False)
        self.verify_button.on_click(self._on_verify_button_clicked)

        # The 'skip' button is only shown when the skip() method is implemented.
        self.skip_button = ipw.Button(description='Skip',
                                      icon='fast-forward',
                                      button_style='info',
                                      layout=ipw.Layout(width='auto',
                                                        flex="1 1 auto"),
                                      disabled=True)
        if self.skip:  # skip() method is implemented
            # connect with skip_button
            self.skip_button.on_click(self.skip)  # connect with skip_button
        else:  # skip() not implemented
            # hide the button
            self.skip_button.layout.visibility = 'hidden'

        # Place all buttons at the footer of the widget.
        self.buttons = ipw.HBox(
            children=[self.verify_button, self.skip_button])

        self.config_tabs = ipw.Tab(
            children=[self.settings, self.code_group, self.resources, self.set_extra_metadata],
            layout=ipw.Layout(min_height='250px'),
        )
        self.config_tabs.set_title(0, 'Verification Setting')
        self.config_tabs.set_title(1, 'Codes Setting')
        self.config_tabs.set_title(2, 'Compute Resources Setting')
        self.config_tabs.set_title(3, 'Extra Metadata')

        # this is for display the information read from the pseudopotential file, element and pp_type etc.
        self.basic_pseudo_info = ipw.Label('')
        self.basic_pseudo_info.layout.visibility = "hidden"

        description = ipw.Label(
            'Specify the parameters and options for the calculation and then click on "Verify".'
        )

        self._submission_blocker_messages = ipw.HTML()

        super().__init__(
            children=[
                self.basic_pseudo_info, 
                description, 
                self.config_tabs,
                self._submission_blocker_messages, 
                self.buttons,
            ], **kwargs)

    @traitlets.observe("state")
    def _observe_state(self, change):
        with self.hold_trait_notifications():
            self.disabled = change["new"] not in (
                self.State.READY,
                self.State.CONFIGURED,
            )
            self.verify_button.disabled = change["new"] != self.State.CONFIGURED

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

    def _on_delta_factor_checkbox_change(self, change):
        """If cohesive checkbox is clicked."""
        if change['new']:
            self.properties_list.append('delta_factor')
        else:
            self.properties_list.remove('delta_factor')

    def _on_cohesive_energy_checkbox_change(self, change):
        """If cohesive checkbox is clicked."""
        if change['new']:
            self.properties_list.append('convergence:cohesive_energy')
        else:
            self.properties_list.remove('convergence:cohesive_energy')

    def _on_phonon_frequencies_checkbox_change(self, change):
        """If phonon checkbox is clicked."""
        if change['new']:
            self.ph_code.layout.visibility = "visible"
            self.properties_list.append('convergence:phonon_frequencies')
        else:
            self.ph_code.layout.visibility = "hidden"
            self.properties_list.remove('convergence:phonon_frequencies')

    def _on_pressure_checkbox_change(self, change):
        """If pressure checkbox is clicked."""
        if change['new']:
            self.properties_list.append('convergence:pressure')
        else:
            self.properties_list.remove('convergence:pressure')

    def _update_total_num_cpus(self, _):
        self.total_num_cpus.value = self.number_of_nodes.value * self.cpus_per_node.value

    def _on_verify_button_clicked(self, _):
        self.verify_button.disabled = True
        self.verify()

    def verify(self):
        """Run the workflow to calculate delta factor"""
        builder = VerificationWorkChain.get_builder()

        builder.pseudo = self.input_pseudo
        builder.pw_code = self.pw_code.selected_code
        builder.ph_code = self.ph_code.selected_code

        builder.protocol = orm.Str(self.protocol.value)
        builder.dual = orm.Float(self.dual.value)
        builder.properties_list = orm.List(list=self.properties_list)

        builder.options = orm.Dict(dict=self.options)
        builder.parallelization = orm.Dict(dict={})
        builder.clean_workdir = orm.Bool(True)

        self.process = submit(builder)

        # set extras for easy query and comprehensive show results
        extras = {
            'element': self.query_pp_element.value,
            'pp_type': self.query_pp_type.value,
            'pp_family': self.query_pp_family.value,
            'pp_version': self.query_pp_version.value,
            'pp_filename': self.input_pseudo.filename,
            'pp_label': self.extra_label.value,
            }
        self.process.set_extra_many(extras)

        self.process.description = self.extra_description

    @traitlets.observe('process')
    def _observe_process(self, change):
        with self.hold_trait_notifications():
            process_node = change['new']
            if process_node is not None:
                self.input_pseudo = process_node.inputs.pseudo
                # TODO: I can do builder parameters setting here
            self._update_state()

    @traitlets.observe("input_pseudo")
    def _observe_input_pseudo(self, change):
        # self.set_input_parameters(DEFAULT_PARAMETERS)
        self._update_state()
        # self._set_num_mpi_tasks_to_default()

        # update extra and description
        if change['new']:
            pseudo = change['new']
            upf_header = helper_parse_upf(pseudo)
            pp_type = upf_header['pseudo_type']

            self.query_pp_element.value = pseudo.element
            self.query_pp_type.value = pp_type

            # set dual upon pp type
            if pp_type == 'NC':
                self.dual.value = 4
            else:
                self.dual.value = 8

            # display description on step 2
            self.basic_pseudo_info.layout.visibility = 'visible'
            self.basic_pseudo_info.value = f'The pseudopotential you uploaded: element={pseudo.element}, pp_type={pp_type}'


    def _get_state(self):
        # Process is already running.
        if self.process is not None:
            return self.State.SUCCESS

        # Input structure not specified.
        if self.input_pseudo is None:
            self._submission_blockers = ["No pseudo selected."]
            # This blocker is handled differently than the other blockers,
            # because it is displayed as INIT state.
            return self.State.INIT

        blockers = list(self._identify_submission_blockers())
        if any(blockers):
            self._submission_blockers = blockers
            return self.State.READY
        else:
            self._submission_blockers = []
            return self.state.CONFIGURED

    def _update_state(self, _=None):
        self.state = self._get_state() 

    def _identify_submission_blockers(self):
        # No input pseudo specified.
        if self.input_pseudo is None:
            yield "No pseudo selected."

        # No code selected (this is ignored while the setup process is running).
        if (
            self.code_group.children[0].selected_code is None
        ):
            yield (
                'No pw.x code selected. Go to "Codes & '
                'Resources" to select a pw code.'
            )

        if (
            self.code_group.children[1].selected_code is None
        ):
            yield (
                'No ph.x code selected. Go to "Codes & '
                'Resources" to select a ph code.'
            )

    @property
    def options(self):
        return {
            # 'max_wallclock_seconds': self.max_wallclock_seconds.value,
            'resources': {
                'num_machines': self.number_of_nodes.value,
                'num_mpiprocs_per_machine': self.cpus_per_node.value
            }
        }

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