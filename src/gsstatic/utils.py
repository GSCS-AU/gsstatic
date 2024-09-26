import functools
from importlib import import_module
import sys
import os

from markupsafe import Markup


def load_class(path):
    """
    Load class from path.
    """

    try:
        mod_name, klass_name = path.rsplit('.', 1)
        mod = import_module(mod_name)
    except AttributeError as e:
        raise ImportError(f'Error importing {mod_name}: "{e}"')

    try:
        klass = getattr(mod, klass_name)
    except AttributeError:
        raise ImportError(f'Module "{mod_name}" does not define a "{klass_name}" class')

    return klass


def safe(function):
    @functools.wraps(function)
    def _decorator(*args, **kwargs):
        return Markup(function(*args, **kwargs))
    return _decorator


def reraise(tp, value, tb=None):
    if value is None:
        value = tp()
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


def cached_import(module_path, class_name):
    # Check whether module is loaded and fully initialized.
    if not (
        (module := sys.modules.get(module_path))
        and (spec := getattr(module, "__spec__", None))
        and getattr(spec, "_initializing", False) is False
    ):
        module = import_module(module_path)
    return getattr(module, class_name)


def import_string(dotted_path):
    """
    Import a dotted module path and return the attribute/class designated by the
    last name in the path. Raise ImportError if the import failed.
    """
    try:
        module_path, class_name = dotted_path.rsplit(".", 1)
    except ValueError as err:
        raise ImportError("%s doesn't look like a module path" % dotted_path) from err

    try:
        return cached_import(module_path, class_name)
    except AttributeError as err:
        raise ImportError(
            'Module "%s" does not define a "%s" attribute/class'
            % (module_path, class_name)
        ) from err
    

def get_exception_info(exception):
    """
    Formats exception information for display on the debug page using the
    structure described in the template API documentation.
    """
    context_lines = 10
    lineno = exception.lineno
    if exception.source is None:
        if os.path.exists(exception.filename):
            with open(exception.filename) as f:
                source = f.read()
    else:
        source = exception.source
    lines = list(enumerate(source.strip().split("\n"), start=1))
    during = lines[lineno - 1][1]
    total = len(lines)
    top = max(0, lineno - context_lines - 1)
    bottom = min(total, lineno + context_lines)

    return {
        'name': exception.filename,
        'message': exception.message,
        'source_lines': lines[top:bottom],
        'line': lineno,
        'before': '',
        'during': during,
        'after': '',
        'total': total,
        'top': top,
        'bottom': bottom,
    }