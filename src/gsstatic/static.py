import jinja2

from . import utils
from . import library
from .reloader import Reloader

from importlib import import_module

from markupsafe import Markup, escape
import re
import os
import sys
import inspect

from pathlib import Path

import logging

default_options = {
    'template_dirs': [], # A list of additional template directories outside the main source directory to search for templates.
    'input_dir': './input/', # The directory to search for templates. This is the root/first directory to search for templates.
    'output_dir': './output/', # The directory to output rendered templates to. Created if needed.
    'context_callable': None, # dotted path to a callable that returns a dict, passed a template_name
    'match_regex': None, # If specified only files that match this regex will be rendered. If None all files will be rendered.
    'environment': 'jinja2.Environment',
    'filters': {
        # 'myfilter': 'path.to.my.filter',
    },
    'tests': {
        # "mytest": "path.to.my.test",
    },
    'globals': {
        # "myglobal": "path.to.my.global",
    },
    'constants': {
        # "myconstant": "myconstant",
    },
    'policies': {
        # See https://jinja.palletsprojects.com/en/3.1.x/api/#policies
    },
    'tags_dir': None, # path to a directory containing custom jinja tags, filters, etc.
    'debug': True,
    'log_level': 'debug',
    'delay': 0.3,
    # Jinja 2 Enviroment Options
    'undefined': None,
    'loader': 'jinja2.FileSystemLoader',
    'extensions': [  
        "jinja2.ext.do",
        "jinja2.ext.loopcontrols",
        "jinja2.ext.i18n",
    ],
    'auto_reload': True, # Given the static nature of this, it shouldnt be required.
    'autoescape': True,
    'trim_blocks': False,
    'lstrip_blocks': False,
    'bytecode_cache': 'jinja2.BytecodeCache',
    
}

class Site(object):
    def __init__(self, options=default_options):

        # Debug
        self.debug = options.pop("debug", True)

        # Paths
        self.input_dir = options.pop("input_dir", default_options['input_dir'])
        if not os.path.exists(self.input_dir):
            raise ValueError(f"Input directory {self.input_dir} does not exist")
        self.output_dir = options.pop("output_dir", default_options['output_dir'])
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        self.cwd = os.getcwd()

        # Context
        self.context_callable = options.pop("context_callable", default_options['context_callable'])
        if self.context_callable is not None and isinstance(self.context_callable, str):
            self.context_callable = utils.load_class(self.context_callable)
        else:
            self.context_callable = lambda x: {}

        # Logging
        _log_level = options.pop("log_level", default_options['log_level'])
        log_level_mapping = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL,
            'fatal': logging.FATAL,
        }
        self.log_level = log_level_mapping.get(_log_level.lower(), logging.DEBUG)
        logging.basicConfig(level=self.log_level)

        self.logger = logging.getLogger(__name__)

        # Jinja 2 Template Directories
        self.template_dirs = options.pop("template_dirs", default_options['template_dirs'])
        
        # Template Match Regex Extension
        self.match_regex = options.pop("match_regex", default_options['match_regex'])
        if self.match_regex:
            self.logger.debug('Match regex: %s', self._match_regex)
            self.match_regex = re.compile(self.match_regex)

        # Jinja 2 Environment Addins
        self.environment_clspath = options.pop("environment", default_options['environment'])
        self.extra_filters = options.pop("filters", default_options['filters'])
        self.extra_tests = options.pop("tests", default_options['tests'])
        self.extra_globals = options.pop("globals", default_options['globals'])
        self.extra_constants = options.pop("constants", default_options['constants'])
        
        # Tags Directory
        self.tags_dir = options.pop("tags_dir", default_options['tags_dir'])

        # Reload Delay
        self.delay = options.pop("delay", default_options['delay'])
        
        # Jinja 2 Environment Options (See Jinja 2 Documentation)
        self.extensions = options.pop("extensions", default_options['extensions'])
        
        self.bytecode_cache_clspath = options.pop("bytecode_cache", default_options['bytecode_cache'])
        if isinstance(self.bytecode_cache_clspath, str):
            self.bytecode_cache_cls = utils.import_string(self.bytecode_cache_clspath)
        else:
            self.bytecode_cache_cls = self.bytecode_cache_clspath

        self.policies = options.pop("policies", default_options['policies'])

        self.undefined = options.pop("undefined", default_options['undefined'])
        if self.undefined is not None:
            if isinstance(self.undefined, str):
                options["undefined"] = utils.load_class(self.undefined)
            else:
                options["undefined"] = self.undefined

        if self.undefined is None:
            if self.debug:
                options.setdefault("undefined", jinja2.DebugUndefined)
            else:
                options.setdefault("undefined", jinja2.Undefined)

        self.environment_cls = utils.import_string(self.environment_clspath)

        self.loader_clspath = options.pop("loader", default_options['loader'])
        if isinstance(self.loader_clspath, str):
            # Allow to specify a loader as string
            self.loader_cls = utils.import_string(self.loader_clspath)
        else:
            self.loader_cls = self.loader_clspath
            if self.loader_cls is None:
                self.loader_cls = jinja2.FileSystemLoader
        
        self.autoreload = options.pop("auto_reload", default_options['auto_reload'])
        self.autoescape = options.pop("autoescape", default_options['autoescape'])
        self.trim_blocks = options.pop("trim_blocks", default_options['trim_blocks'])
        self.lstrip_blocks = options.pop("lstrip_blocks", default_options['lstrip_blocks'])


        env_options = {}
        if inspect.isclass(self.loader_cls):
            # If the loader is a class we instantiate it with the template dirs
            env_options["loader"] = self.loader_cls([self.input_dir] + self.template_dirs)
        else:
            # If the loader is an instance or string we pass it as is
            env_options["loader"] = self.loader_cls
        env_options["extensions"] = self.extensions
        env_options["auto_reload"] = self.debug or self.autoreload
        env_options["autoescape"] = True
        env_options["trim_blocks"] = False
        env_options["lstrip_blocks"] = False
        env_options["bytecode_cache"] = self.bytecode_cache_cls

        self.env = self.environment_cls(**env_options)

        self._initialize_builtins(filters=self.extra_filters,
                                  tests=self.extra_tests,
                                  globals=self.extra_globals,
                                  constants=self.extra_constants)
        self._initialize_policies(self.policies)

        self._initialize_thirdparty()

    def _initialize_thirdparty(self):
        """
        Iterate over all available apps in searching and preloading
        available template filters or functions for jinja2.
        """
        if self.tags_dir is not None and os.path.exists(self.tags_dir):
            for filename in filter(lambda x: x.endswith(".py") or x.endswith(".pyc"), os.listdir(self.tags_dir)):
                self.logger.debug(f'Evaluating thirdparty module {filename}')
                # Exclude __init__.py files
                if filename == "__init__.py" or filename == "__init__.pyc":
                    continue
                # Convert to relative path and generate module path
                relative_file_path = Path(self.tags_dir).joinpath(filename).absolute().relative_to(self.cwd)
                file_mod_path = '.'.join(relative_file_path.parts).replace('.py', '').replace('.pyc', '')
                
                try:
                    self.logger.debug(f'Importing thirdparty module {file_mod_path}')
                    import_module(file_mod_path)
                except ImportError:
                    self.logger.debug(f'Error importing thirdparty module {file_mod_path}')
                    pass

            library._update_env(self.env)

    def _initialize_builtins(self, filters=None, tests=None, globals=None, constants=None):
        self.logger.info('Initializing builtins')
        def insert(data, name, value):
            if isinstance(value, str):
                data[name] = utils.import_string(value)
            else:
                data[name] = value

        if filters:
            for name, value in filters.items():
                self.logger.debug(f'Adding filter {name} to env')
                insert(self.env.filters, name, value)

        if tests:
            for name, value in tests.items():
                self.logger.debug(f'Adding test {name} to env')
                insert(self.env.tests, name, value)

        if globals:
            for name, value in globals.items():
                self.logger.debug(f'Adding global {name} to env')
                insert(self.env.globals, name, value)

        if constants:
            for name, value in constants.items():
                self.logger.debug(f'Adding constant {name} to env')
                self.env.globals[name] = value

    def _initialize_policies(self, policies):
        self.logger.info('Initializing policies')
        # Set policies like those in jinja2.defaults.DEFAULT_POLICIES
        for name, value in policies.items():
            self.env.policies[name] = value

    def match_template(self, template_name):
        '''Check if the given template_name matches the configured extension and regex.'''
        self.logger.info(f'Matching template {template_name}')
        if self.match_regex:
            return re.match(self.match_regex, template_name)
        else:
            return True

    def get_template(self, template_name):
        '''Get a template by name, raising a TemplateNotFound exception if it does not exist.'''
        self.logger.info(f'Getting template {template_name}')
        try:
            return self.env.get_template(template_name)
        except jinja2.TemplateNotFound as exc:
            # Unlike django's template engine, jinja2 doesn't like windows-style path separators.
            # But because django does, its docs encourage the usage of os.path.join().
            # Rather than insisting that our users switch to posixpath.join(), this try block
            # will attempt to retrieve the template path again with forward slashes on windows:
            if os.name == 'nt' and '\\' in template_name:
                try:
                    return self.get_template(template_name.replace("\\", "/"))
                except jinja2.TemplateNotFound:
                    # Raise for the original name
                    raise jinja2.TemplateNotFound(template_name)
        except jinja2.TemplateSyntaxError as exc:
            new = jinja2.TemplateSyntaxError(exc.args)
            new.template_debug = utils.get_exception_info(exc)
            utils.reraise(jinja2.TemplateSyntaxError, new, sys.exc_info()[2])
        
    def render_templates(self):
        '''Walk through the template directory and render all matching templates to the output directory.
        Maintain the directory structure of the input directory in the output directory.
        If the output directory does not exist create it before rendering the templates.'''
        self.logger.info('Rendering templates')

        for root, dirs, files in os.walk(self.input_dir):
            self.logger.debug(f'Walking through {root}')
            for file in files:
                self.logger.debug(f'Checking file {file}')
                if self.match_template(file):
                    self.logger.debug(f'Rendering template {file}')
                    template_name = os.path.relpath(os.path.join(root, file), self.input_dir)
                    self.render_template(template_name)
                                                                           
    def check_output_dir(self):
        '''Check if the output directory exists, if not create it.'''
        self.logger.info('Checking output directory')
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)                                  

    def render_template(self, template_name):
        '''Given a root directory (within self.input_dir) and a file name, 
        render the template and output the rendered template to the 
        output directory, creating any output directories that do not exist.'''
        self.logger.info(f'Rendering template {template_name}')
        template = self.get_template(template_name)
        self.logger.debug('Template: %s', template)
        output_file = os.path.join(self.output_dir, template_name)
        output_dir = os.path.dirname(output_file)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with open(output_file, 'w') as f:
            ctx = self.context_callable(template_name)
            self.logger.debug('Context: %s', ctx)
            f.write(template.render(ctx))
        
    def make(self, watch=False):
        self.check_output_dir()

        self.render_templates()

        if watch:
            Reloader(self).watch()
