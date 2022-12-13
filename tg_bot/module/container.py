import typing as tp
import logging

logger = logging.getLogger(__name__)


class ModuleContainer:
    def __init__(self):
        self._modules = {}

    def add_module(self, module: "BasicModule"):
        module_name = type(module).__name__
        if module_name in self._modules:
            raise ValueError(f"Module '{module_name}' was already registered")
        self._modules[module_name] = module

    def find_module(self, cls: type) -> tp.Optional[tp.Any]:
        if cls.__name__ not in self._modules:
            logger.warning(f"Unable to find module '{cls.__name__}'")

        return self._modules.get(cls.__name__)

    def initialize(self):
        for module in self._modules.values():
            module._initialize()
