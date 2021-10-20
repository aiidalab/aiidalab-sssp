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

    skip = False

    def __init__(self, **kwargs):
        pw_code = CodeDropdown(input_plugin='quantumespresso.pw',
                               description="PW code")
        self.ph_code = CodeDropdown(input_plugin='quantumespresso.ph',
                               description="PH code")

        self.code_group = ipw.VBox(children=[pw_code, self.ph_code])

        protocol_list = ['efficiency', 'precision', 'test'] # will read from sssp plugin
        properties_list = ['Delta factor', 'Convergence: Cohesive Energy',
            'Convergence: Bands Distance', 'Convergence: Pressure']

        phonon_checkbox = ipw.Checkbox(value=True, description='Convergence: Phonon Frequencies')
        phonon_checkbox.observe(self.on_phonon_checkbox_change, names="value")

        self.properties = [ipw.Checkbox(value=True, description=label) for label in properties_list] + [phonon_checkbox]

        option_box_extra = {
            'style': {
                'description_width': '120px'
            },
            'layout': {
                'max_width': '210px'
            }
        }

        self.protocol = ipw.Dropdown(
            options=protocol_list,
            value='test',
            description='Protocol:',
            disabled=False,
            **option_box_extra)

        self.dual= ipw.BoundedIntText(
            value=8,
            step=1,
            min=1,
            description="# dual",
            **option_box_extra)

        self.query_pp_element = ipw.Text(
            value='Unknown',
            placeholder='The element of the pseudo',
            description='Element:',
            disabled=False
        )
        self.query_pp_type = ipw.Text(
            value='Unknown',
            placeholder='The type of the pseudo',
            description='PP type:',
            disabled=False
        )
        self.query_pp_family = ipw.Text(
            value='UnKnown',
            placeholder='The family name of the pseudo',
            description='Family name:',
            disabled=False
        )
        self.query_pp_version = ipw.Text(
            value='UnKnown',
            placeholder='The version number of the pseudo',
            description='Version:',
            disabled=False
        )

        # the settings for protocol choose (dropdown) and properties (checkboxes) and infos for query
        self.settings = ipw.HBox(children=[
            ipw.VBox(
                children=self.properties,
            ),
            ipw.VBox(
                children=[
                    self.protocol,
                    self.dual,
                ],
            ),
            ipw.VBox(
                children=[
                    self.query_pp_element,
                    self.query_pp_type,
                    self.query_pp_family,
                    self.query_pp_version,
                ],
            ),
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
            children=[self.settings, self.code_group, self.resources],
            layout=ipw.Layout(height='240px'),
        )
        self.config_tabs.set_title(0, 'Verification Setting')
        self.config_tabs.set_title(1, 'Codes Setting')
        self.config_tabs.set_title(2, 'Compute Resources Setting')

        description = ipw.Label(
            'Specify the parameters and options for the calculation and then click on "Verify".'
        )

        super().__init__(
            children=[description, self.config_tabs, self.buttons], **kwargs)

    def on_phonon_checkbox_change(self, change):
        """If phonon checkbox is clicked."""
        if change['new']:
            self.ph_code.layout.visibility = "visible"
        else:
            self.ph_code.layout.visibility = "hidden"

    @traitlets.observe('input_pseudo')
    def _observe_input_pseudo(self, change):
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

    def _update_total_num_cpus(self, _):
        self.total_num_cpus.value = self.number_of_nodes.value * self.cpus_per_node.value

    def _on_verify_button_clicked(self, _):
        self.verify()

    def verify(self):
        """Run the workflow to calculate delta factor"""
        VerificationWorkChain = WorkflowFactory('sssp_workflow.verification')

        if self.input_pseudo is None:
            print('Please set input pseudopotential in previous step.')
        else:
            from aiida.engine import submit

            builder = VerificationWorkChain.get_builder()

            builder.pseudo = self.input_pseudo
            builder.pw_code = self.code_group.children[0].selected_code
            builder.ph_code = self.code_group.children[1].selected_code

            builder.protocol = orm.Str(self.protocol.value)
            builder.dual = orm.Float(self.dual.value)

            builder.options = orm.Dict(dict=self.options)
            builder.parallelization = orm.Dict(dict={})
            builder.clean_workdir = orm.Bool(True)

            self.verify_button.disabled = True

            # print(builder)
            self.process = submit(builder)

            # set extras for easy query and comprehensive show results
            extras = {
                'element': self.query_pp_element.value,
                'pp_type': self.query_pp_type.value,
                'pp_family': self.query_pp_family.value,
                'pp_version': self.query_pp_version.value,
                'pp_filename': self.input_pseudo.filename,
            }
            self.process.set_extra_many(extras)

    @property
    def options(self):
        return {
            # 'max_wallclock_seconds': self.max_wallclock_seconds.value,
            'resources': {
                'num_machines': self.number_of_nodes.value,
                'num_mpiprocs_per_machine': self.cpus_per_node.value
            }
        }