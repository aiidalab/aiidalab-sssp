import ipywidgets as ipw
from widget_periodictable import PTableWidget

__all__ = ("PeriodicTable",)


class PeriodicTable(ipw.VBox):
    """Wrapper-widget for PTableWidget"""

    def __init__(self, extended: bool = True, **kwargs):
        self._disabled = kwargs.get("disabled", False)

        self.select_any_all = ipw.Checkbox(
            value=False,
            description="Structures can include any chosen elements (instead of all)",
            indent=False,
            layout={"width": "auto"},
            disabled=self.disabled,
        )
        self.ptable = PTableWidget(**kwargs)
        self.ptable_container = ipw.VBox(
            children=(self.select_any_all, self.ptable),
            layout={
                "width": "auto",
                "height": "auto" if extended else "0px",
                "visibility": "visible" if extended else "hidden",
            },
        )

        super().__init__(
            children=(self.ptable_container,),
            layout=kwargs.get("layout", {}),
        )

    @property
    def value(self) -> dict:
        """Return value for wrapped PTableWidget"""

        return not self.select_any_all.value, self.ptable.selected_elements.copy()

    @property
    def disabled(self) -> None:
        """Disable widget"""
        return self._disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        """Disable widget"""
        if not isinstance(value, bool):
            raise TypeError("disabled must be a boolean")

        self.select_any_all.disabled = self.ptable.disabled = value

    def reset(self):
        """Reset widget"""
        self.select_any_all.value = False
        self.ptable.selected_elements = {}

    def freeze(self):
        """Disable widget"""
        self.disabled = True

    def unfreeze(self):
        """Activate widget (in its current state)"""
        self.disabled = False
