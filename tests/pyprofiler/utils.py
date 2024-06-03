
import importlib.util
import sys
import inspect
from pathlib import Path


def load_classes_from_file(filename: str, parent_class_name: str):
    """Load subclasses of `parent_class_name` from given filename module"""
    module_name = Path(filename).stem
    spec = importlib.util.spec_from_file_location(module_name, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    # Get the parent class from the module
    parent_class = None
    for name, obj in inspect.getmembers(module, inspect.isclass):
        if name == parent_class_name:
            parent_class = obj
            break

    if not parent_class:
        raise ValueError(
            f"Parent class '{parent_class_name}' not found in {filename}"
        )

    # Get all classes that are subclasses of the parent class
    subclasses = [
        obj for name, obj in inspect.getmembers(module, inspect.isclass)
        if issubclass(obj, parent_class) and obj is not parent_class
    ]

    return subclasses
