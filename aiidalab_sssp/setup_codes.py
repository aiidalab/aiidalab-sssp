# -*- coding: utf-8 -*-
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError, run
from threading import Event, Thread
from time import time

import ipywidgets as ipw
import traitlets
from aiida.common.exceptions import NotExistent
from aiida.orm import load_code
from filelock import FileLock, Timeout

__all__ = [
    "QESetupWidget",
]

FN_LOCKFILE = Path.home().joinpath(".install-qe-on-localhost.lock")
FN_DO_NOT_SETUP = Path.cwd().joinpath(".do-not-setup-on-localhost")

QE_VERSION = "6.7"

CONDA_ENV_PREFIX = Path.home().joinpath(
    ".conda", "envs", f"quantum-espresso-{QE_VERSION}"
)

CODE_NAMES = ("pw", "ph")


def qe_installed():
    return CONDA_ENV_PREFIX.exists()


def install_qe():
    run(
        [
            "conda",
            "create",
            "--yes",
            "--override-channels",
            "--channel",
            "conda-forge",
            "--prefix",
            str(CONDA_ENV_PREFIX),
            f"qe={QE_VERSION}",
        ],
        capture_output=True,
        check=True,
    )


def _code_is_setup(name):
    try:
        load_code(f"{name}-{QE_VERSION}@localhost")
    except NotExistent:
        return False
    else:
        return True


def codes_are_setup():
    return all(_code_is_setup(code_name) for code_name in CODE_NAMES)


def _setup_code(code_name, computer_name="localhost"):
    try:
        load_code(f"{code_name}-{QE_VERSION}@localhost")
    except NotExistent:
        run(
            [
                "verdi",
                "code",
                "setup",
                "--non-interactive",
                "--label",
                f"{code_name}-{QE_VERSION}",
                "--description",
                f"{code_name}.x ({QE_VERSION}) setup by AiiDAlab.",
                "--input-plugin",
                f"quantumespresso.{code_name}",
                "--computer",
                computer_name,
                "--prepend-text",
                f"conda activate {CONDA_ENV_PREFIX}\nexport OMP_NUM_THREADS=1",
                "--remote-abs-path",
                CONDA_ENV_PREFIX.joinpath("bin", f"{code_name}.x"),
            ],
            check=True,
            capture_output=True,
        )
    else:
        raise RuntimeError(f"Code {code_name} (v{QE_VERSION}) is already setup!")


def setup_codes():
    for code_name in CODE_NAMES:
        _setup_code(code_name)


class QESetupWidget(ipw.VBox):

    installed = traitlets.Bool(allow_none=True).tag(readonly=True)
    busy = traitlets.Bool().tag(readonly=True)
    error = traitlets.Unicode().tag(readonly=True)

    def __init__(self, prefix=None, hide_by_default=True, auto_start=True, **kwargs):
        self.prefix = prefix or f"QuantumESPRESSO (v{QE_VERSION}) @localhost: "
        self.hide_by_default = hide_by_default

        self._progress_bar = ProgressBar(
            description=self.prefix,
            description_layout=ipw.Layout(min_width="300px"),
            layout=ipw.Layout(width="auto", flex="1 1 auto"),
        )

        self._info_toggle_button = ipw.ToggleButton(
            icon="info-circle",
            disabled=True,
            layout=ipw.Layout(width="36px"),
        )
        self._info_toggle_button.observe(self._toggle_error_view, "value")

        self._reinstall_button = ipw.Button(
            icon="cogs",
            disabled=True,
            description="Install codes...",
            tooltip="Start another installation attempt.",
        )
        self._reinstall_button.on_click(self._trigger_reinstall)

        self._error_output = ipw.HTML()

        super().__init__(
            [
                ipw.HBox(
                    [self._progress_bar, self._info_toggle_button],
                    layout=ipw.Layout(width="auto"),
                ),
            ],
            **kwargs,
        )

        if auto_start:
            self.refresh()

    def set_message(self, msg):
        self._progress_bar.description = f"{self.prefix}{msg}"

    def _refresh_installed(self):
        AnimationRate = ProgressBar.AnimationRate  # alias
        conda_installed = which("conda")

        self.set_message("checking installation status...")
        try:
            self.set_trait("busy", True)

            # Check for "do not install file" and skip actual check. The purpose of
            # this file is to not re-try this process on every app start in case
            # that there are issues.
            if FN_DO_NOT_SETUP.exists():
                self.set_message("Installation previously failed.")
                self.error = "Installation failed in previous attempt."
                return

            try:
                with FileLock(FN_LOCKFILE, timeout=5):
                    # We assume that if the codes are already setup, everything
                    # is in order. Only if they are not present, should we take
                    # action, however we only do so if the environment has a
                    # conda binary present (`which conda`). If that is not the
                    # case then we assume that this is a custom user environment
                    # in which case we also take no further action.
                    self.installed = codes_are_setup() or not conda_installed
                    if self.installed:
                        self.error = ""
                        self.set_message("Codes are installed.")
                    else:
                        self.error = ""
                        self.set_message("installing...")
                        # To setup our own codes, we install QE on the local
                        # host:
                        if not qe_installed():
                            self.set_message("Installing QE...")
                            self._progress_bar.value = AnimationRate(0.05)
                            try:
                                install_qe()
                            except CalledProcessError as error:
                                raise RuntimeError(
                                    f"Failed to create conda environment: {error}"
                                )
                        self.value = 0.7
                        # After installing QE, we install the corresponding
                        # AiiDA codes:
                        for i, code_name in enumerate(CODE_NAMES):
                            if not _code_is_setup(code_name):
                                self.set_message(
                                    f"Setting up AiiDA code ({code_name})..."
                                )
                                self._progress_bar.value = AnimationRate(0.1)
                                _setup_code(code_name)
                            self.value = 0.8 + i * 0.1
                        # After going through the installation procedure, we
                        # expect both our version of QE to be installed, as well
                        # as the codes to be setup.
                        self.installed = qe_installed() and codes_are_setup()

            except Timeout:
                # assume that the installation was triggered by a different
                # process
                self.set_message("installing...")
                self._progress_bar.value = AnimationRate(0.01)
                with FileLock(FN_LOCKFILE, timeout=120):
                    self.installed = codes_are_setup() or not conda_installed

            # Raise error in case that the installation was not successful
            # either in this process or a different one.
            if not self.installed:
                raise RuntimeError("Installation failed for unknown reasons.")

        except Exception as error:
            self.set_message("Failed to setup QE on localhost.")
            self.set_trait("error", str(error))
            FN_DO_NOT_SETUP.touch()
        else:
            self.set_message("OK")
        finally:
            self.set_trait("busy", False)

    def refresh(self):
        thread = Thread(target=self._refresh_installed)
        thread.start()

    @traitlets.default("installed")
    def _default_installed(self):
        return None

    @traitlets.default("busy")
    def _default_busy(self):
        return False

    @traitlets.default("failed")
    def _default_error(self):
        return ""

    @traitlets.observe("error")
    def _observe_error(self, change):
        with self.hold_trait_notifications():
            self._error_output.value = f"""
            <div class="alert alert-warning">
            <p>Failed to setup QE on localhost, due to error:</p>

            <p><code>{change["new"]}</code></p>

            <hr>
            <p>This means you have to setup QE manually to run it on this host.
            You can safely ignore this message if you do not plan on running
            QuantumESPRESSO calculations directly on the localhost. Alternatively
            you could try to make another installation attempt via the button
            below.</p>
            """
            self._info_toggle_button.disabled = not bool(change["new"])
            self._reinstall_button.disabled = not change["new"]
            if not change["new"]:
                self._info_toggle_button.value = False

    def _toggle_error_view(self, change):
        self.children = [self.children[0]] + (
            [self._error_output, self._reinstall_button] if change["new"] else []
        )

    @traitlets.observe("busy")
    @traitlets.observe("error")
    @traitlets.observe("installed")
    def _update(self, change):
        with self.hold_trait_notifications():
            if self.hide_by_default:
                self.layout.visibility = (
                    "visible" if (self.busy or self.error) else "hidden"
                )

            if self.error or self.installed:
                self._progress_bar.value = 1.0

            self._progress_bar.bar_style = (
                "info"
                if self.busy
                else (
                    "warning"
                    if self.error
                    else {True: "success", False: ""}.get(self.installed, "")
                )
            )

    def _trigger_reinstall(self, _=None):
        FN_DO_NOT_SETUP.unlink()
        self.refresh()


class ProgressBar(ipw.HBox):
    class AnimationRate(float):
        pass

    description = traitlets.Unicode()
    value = traitlets.Union([traitlets.Float(), traitlets.Instance(AnimationRate)])
    bar_style = traitlets.Unicode()

    _animation_rate = traitlets.Float()

    def __init__(self, description_layout=None, *args, **kwargs):
        if description_layout is None:
            description_layout = ipw.Layout(width="auto", flex="2 1 auto")

        self._label = ipw.Label(layout=description_layout)
        self._progress_bar = ipw.FloatProgress(
            min=0, max=1.0, layout=ipw.Layout(width="auto", flex="1 1 auto")
        )

        traitlets.link((self, "description"), (self._label, "value"))
        traitlets.link((self, "bar_style"), (self._progress_bar, "bar_style"))

        self._animate_stop_event = Event()
        self._animate_thread = None

        super().__init__([self._label, self._progress_bar], *args, **kwargs)

    def _animate(self, refresh_rate=0.01):

        v0 = self._progress_bar.value
        t0 = time()

        while not self._animate_stop_event.wait(refresh_rate):
            self._progress_bar.value = (v0 + (time() - t0) * self._animation_rate) % 1.0

    def _start_animate(self):
        if self._animate_thread is not None:
            raise RuntimeError("Cannot start animation more than once!")

        self._animate_thread = Thread(target=self._animate)
        self._animate_thread.start()

    def _stop_animate(self):
        self._animate_stop_event.set()
        self._animate_thread.join()
        self._animate_stop_event.clear()
        self._animate_thread = None

    @traitlets.default("_animation_rate")
    def _default_animation_rate(self):
        return 0

    @traitlets.observe("_animation_rate")
    def _observe_animation_rate(self, change):
        if change["new"] and not change["old"]:
            self._start_animate()
        elif not change["new"] and change["old"]:
            self._stop_animate()

    @traitlets.validate("value")
    def _validate_value(self, proposal):
        if isinstance(proposal["value"], self.AnimationRate):
            if proposal["value"] < 0:
                raise traitlets.TraitError("The animation rate must be non-negative.")

        elif not 0 <= proposal["value"] <= 1.0:
            raise traitlets.TraitError("The value must be between 0 and 1.0.")

        return proposal["value"]

    @traitlets.observe("value")
    def _observe_value(self, change):
        if isinstance(change["new"], self.AnimationRate):
            self._animation_rate = change["new"]
        else:
            self._animation_rate = 0
            self._progress_bar.value = change["new"]
