from importlib import resources

import yaml

from aiidalab_sssp import parameters

DEFAULT_PARAMETERS = yaml.safe_load(resources.read_text(parameters, "ssspapp.yaml"))
