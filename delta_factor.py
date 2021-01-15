"""Widget for delta factor calculation"""
import ipywidgets as ipw
import traitlets

from aiidalab_widgets_base import CodeDropdown

from aiida.plugins import DataFactory, WorkflowFactory
from aiida.engine import submit
from aiida import orm

UpfData = DataFactory('upf')


class ComputeDeltaFactorWidget(ipw.VBox):
    """ComputeDeltaFactorWidget"""

    process = traitlets.Instance(orm.ProcessNode, allow_none=True)
    input_pseudo = traitlets.Instance(UpfData, allow_none=True)
    disabled = traitlets.Bool()

    skip = False

    def __init__(self, **kwargs):
        setup_code_params = {
            "computer": "localhost",
            "description": "pw.x in AiiDAlab container.",
            "label": "pw",
            "input_plugin": "quantumespresso.pw",
            'remote_abs_path': '/usr/bin/pw.x',
        }
        self.code_group = CodeDropdown(input_plugin='quantumespresso.pw',
                                       text="Select code",
                                       setup_code_params=setup_code_params)

        parameters_setting_prompt = ipw.HTML(
            "Select the compute parameters for this calculation.")
        parameters_setting_help = ipw.HTML(
            """<div style="line-height:120%; padding-top:25px;">
            <p>Parameters and their meaning in delta factor calculation:</p>
            <ul>
            <li>protocol: .</li>
            <li>kpoints_distance: .</li>
            <li>... .</li>
            </ul>
            <p>However, specifying the optima.</p></div>""")

        extra = {
            'style': {
                'description_width': '150px'
            },
            'layout': {
                'max_width': '1000px'
            }
        }

        self.protocol = ipw.Dropdown(
            options=['None', 'efficiency', 'precision'],
            value='None',
            description='Protocol:',
            disabled=False,
            **extra)
        self.kpoints_distance = ipw.BoundedFloatText(
            value=0.10,
            min=0.05,
            max=0.5,
            step=0.05,
            description='Kpoints distance:',
            disabled=False,
            **extra)
        self.ecutwfc = ipw.BoundedIntText(value=200,
                                          min=10,
                                          max=300,
                                          step=1,
                                          description='ecutwfc:',
                                          disabled=False,
                                          **extra)
        self.ecutrho = ipw.BoundedIntText(value=800,
                                          min=10,
                                          max=10000,
                                          step=1,
                                          description='ecutrho:',
                                          disabled=False,
                                          **extra)
        self.scale_count = ipw.BoundedIntText(value=7,
                                              min=3,
                                              max=20,
                                              step=1,
                                              description='EOS points:',
                                              disabled=False,
                                              **extra)
        self.scale_increment = ipw.FloatText(
            value=0.02,
            description='EOS scale increment:',
            disabled=False,
            **extra)
        self.smearing_type = ipw.Dropdown(options=[
            'gaussian', 'methfessel-paxton', 'marzari-vanderbilt',
            'fermi-dirac'
        ],
                                          value='methfessel-paxton',
                                          description='smearing type:',
                                          disabled=False,
                                          **extra)
        self.smearing = ipw.FloatText(value=0.00735,
                                      description='smearing width:',
                                      disabled=False,
                                      **extra)

        # update setting area upon if protocol set
        ipw.dlink((self, 'disabled'), (self.kpoints_distance, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.ecutwfc, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.ecutrho, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.scale_count, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.scale_increment, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.smearing, 'disabled'))
        ipw.dlink((self, 'disabled'), (self.smearing_type, 'disabled'))

        self.protocol.observe(self._observe_protocol, 'value')

        # set the parameters for delta factor calculation
        self.parameters = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    parameters_setting_prompt,
                    self.protocol,
                    self.kpoints_distance,
                    self.ecutwfc,
                    self.ecutrho,
                    self.scale_count,
                    self.scale_increment,
                    self.smearing_type,
                    self.smearing,
                ],
                layout=ipw.Layout(min_width='310px'),
            ),
            parameters_setting_help,
        ])

        extra = {
            'style': {
                'description_width': '150px'
            },
            'layout': {
                'max_width': '240px'
            }
        }

        self.number_of_nodes = ipw.BoundedIntText(value=1,
                                                  step=1,
                                                  min=1,
                                                  description="# nodes",
                                                  disabled=False,
                                                  **extra)
        self.cpus_per_node = ipw.BoundedIntText(value=1,
                                                step=1,
                                                min=1,
                                                description="# cpus per node",
                                                **extra)
        self.total_num_cpus = ipw.BoundedIntText(value=1,
                                                 step=1,
                                                 min=1,
                                                 description="# total cpus",
                                                 disabled=True,
                                                 **extra)
        self.max_wallclock_seconds = ipw.BoundedIntText(
            value=3600,
            step=1,
            min=1,
            max=36000,
            description="# max wallclock seconds",
            disabled=False,
            **extra)

        # Update the total # of CPUs int text:
        self.number_of_nodes.observe(self._update_total_num_cpus, 'value')
        self.cpus_per_node.observe(self._update_total_num_cpus, 'value')

        resource_selection_prompt = ipw.HTML(
            "Select the compute resources for this calculation.")
        resource_selection_help = ipw.HTML(
            """<div style="line-height:120%; padding-top:25px;">
            <p>There is no general rule of thumb on how to select the appropriate number of
            nodes and cores. In general:</p>
            <ul>
            <li>Increase the number of nodes if you run out of memory for larger structures.</li>
            <li>Increase the number of nodes and cores if you want to reduce the total runtime.</li>
            </ul>
            <p>However, specifying the optimal configuration of resources is a complex issue and
            simply increasing either cores or nodes may not have the desired effect.</p></div>"""
        )
        self.resources = ipw.HBox(children=[
            ipw.VBox(
                children=[
                    resource_selection_prompt,
                    self.number_of_nodes,
                    self.cpus_per_node,
                    self.max_wallclock_seconds,
                    self.total_num_cpus,
                ],
                layout=ipw.Layout(min_width='360px'),
            ),
            resource_selection_help,
        ])

        # Clicking on the 'submit' button will trigger the execution of the
        # submit() method.
        self.submit_button = ipw.Button(
            description='Submit',
            tooltip="Submit the calculation with the selected parameters.",
            icon='play',
            button_style='success',
            layout=ipw.Layout(width='auto', flex="1 1 auto"),
            disabled=False)
        self.submit_button.on_click(self._on_submit_button_clicked)

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
            children=[self.submit_button, self.skip_button])

        self.config_tabs = ipw.Tab(
            children=[self.code_group, self.parameters, self.resources],
            layout=ipw.Layout(height='320px'),
        )
        self.config_tabs.set_title(0, 'Code')
        self.config_tabs.set_title(1, 'Parameters')
        self.config_tabs.set_title(2, 'Compute resources')

        description = ipw.Label(
            'Specify the parameters and options for the calculation and then click on "Submit".'
        )

        super().__init__(
            children=[description, self.config_tabs, self.buttons], **kwargs)

    def _update_total_num_cpus(self, _):
        self.total_num_cpus.value = self.number_of_nodes.value * self.cpus_per_node.value

    def _on_submit_button_clicked(self, _):
        self.submit()

    def submit(self):
        """Run the workflow to calculate delta factor"""
        if self.input_pseudo is None:
            print('Please set input pseudopotential in previous step.')
        else:
            builder = WorkflowFactory(
                'sssp_workflow.delta_factor').get_builder()

            builder.pseudo = self.input_pseudo
            builder.code = self.code_group.selected_code

            if self.protocol.value != 'None':
                builder.protocol = orm.Str(self.protocol.value)
            else:
                parameters = {
                    'SYSTEM': {
                        'occupations': 'smearing',
                        'degauss': self.smearing.value,
                        'smearing': self.smearing_type.value,
                    },
                }
                builder.parameters.pw = orm.Dict(dict=parameters)
                builder.parameters.ecutwfc = orm.Int(self.ecutwfc.value)
                builder.parameters.ecutrho = orm.Int(self.ecutrho.value)

                builder.parameters.kpoints_distance = orm.Float(
                    self.kpoints_distance.value)
                builder.parameters.scale_count = orm.Int(
                    self.scale_count.value)
                builder.parameters.scale_increment = orm.Float(
                    self.scale_increment.value)

            builder.options = orm.Dict(dict=self.options)
            builder.clean_workdir = orm.Bool(True)

            self.submit_button.disabled = True

            # print(builder)
            self.process = submit(builder)

    def _observe_protocol(self, change):
        if change['new'] != 'None':
            self.disabled = True
        else:
            self.disabled = False

    @property
    def options(self):
        return {
            'max_wallclock_seconds': self.max_wallclock_seconds.value,
            'resources': {
                'num_machines': self.number_of_nodes.value,
                'num_mpiprocs_per_machine': self.cpus_per_node.value
            }
        }
