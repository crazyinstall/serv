import pkgutil
import os
import json
import sys
from distutils.spawn import find_executable
import tempfile
import shutil

import jinja2


class Base(object):
    def __init__(self, lgr=None, **params):
        self.lgr = lgr
        self.params = params

        self.init_sys = params.get('init_sys')
        self.init_sys_ver = params.get('init_sys_ver')
        self.cmd = params.get('cmd')
        self.name = params.get('name')
        self._set_default_parameter_values()

        self._validate_init_system_params()

    def _set_default_parameter_values(self):
        p = self.params
        p['description'] = p.get('description', 'no description given')
        p['chdir'] = p.get('chdir', '/')
        p['chroot'] = p.get('chroot', '/')
        p['user'] = p.get('user', 'root')
        p['group'] = p.get('group', 'root')

    def _validate_init_system_params(self):
        niceness = self.params.get('nice')
        if niceness in self.params and (niceness < -20 or niceness > 19):
            self.lgr.error('`niceness` level must be between -20 and 19.')
            sys.exit()
        # WIP!
        if 0 == 1:
            limit_params = [
                'limit_coredump',
                'limit_cputime',
                'limit_data',
                'limit_file_size',
                'limit_locked_memory',
                'limit_open_files',
                'limit_user_processes',
                'limit_physical_memory',
                'limit_stack_size',
            ]
            limits = [self.params.get(l) for l in limit_params]
            for l in limit_params:
                if l in self.params and int(self.params.get(l, '')) < 1:
                    self.lgr.error('All limits must be greater than 0.')
                    sys.exit()

            if not any(limits):
                self.lgr.error('All limits must be greater than 0.')
                self.exit()

    def generate(self, overwrite):
        """Generates service files.
        """
        self.tmp = tempfile.gettempdir()
        self.tempaltes = os.path.join(os.path.dirname(__file__), 'templates')
        self.overwrite = overwrite

    def install(self):
        """Installs a service on the local machine.

        This is relevant for init systems like systemd where you have to
        `sudo systemctl enable #SERVICE#` before starting a service.
        """
        if not find_executable(self.cmd):
            self.lgr.error('Executable {0} could not be found.'.format(
                self.cmd))
            sys.exit()

    def start(self):
        """Starts a service.
        """
        raise NotImplementedError('Must be implemented by a subclass')

    def stop(self):
        """Stops a service.
        """
        raise NotImplementedError('Must be implemented by a subclass')

    def uninstall(self):
        """Uninstalls a service.

        This should include any cleanups required.
        """
        raise NotImplementedError('Must be implemented by a subclass')

    def status(self, name=''):
        """Retrieves the status of a service `name` or all services
        for the current init system.
        """
        self.services = dict(
            init_system=self.init_sys,
            init_system_version=self.init_sys_ver,
            services=[]
        )

    def is_system_exists(self):
        """Returns True if the init system exists on the current machine
        or False if it doesn't.
        """
        raise NotImplementedError('Must be implemented by a subclass')

    def is_service_exists(self):
        """Returns True if the service is installed on the current machine
        and False if it isn't.
        """
        raise NotImplementedError('Must be implemented by a subclass')

    def generate_file_from_template(self, template, destination):
        """Generates a file from a Jinja2 `template` and writes it to
        `destination` using `params`.

        `overwrite` allows to overwrite existing files. It is passed to
        the `generate` method.

        This is used by the different init implementations to generate
        init scripts/configs and deploy them to the relevant directories.
        Templates are looked up under init/templates/`template`.

        If the `destination` directory doesn't exist, it will alert
        the user and exit. We don't want to be creating any system
        related directories out of the blue. The exception to the rule is
        with nssm.
        While it may seem a bit weird, not all relevant directories exist
        out of the box. For instance, `/etc/sysconfig` doesn't necessarily
        exist even if systemd is used by default.
        """
        templates = pkgutil.get_data(__name__, os.path.join(
            'templates', template))

        pretty_params = json.dumps(self.params, indent=4, sort_keys=True)
        self.lgr.debug('Rendering {0} with params: {1}...'.format(
            template, pretty_params))
        generated = jinja2.Environment().from_string(
            templates).render(self.params)
        self.lgr.debug('Writing generated file to {0}...'.format(destination))
        self._should_overwrite(destination)
        with open(destination, 'w') as f:
            f.write(generated)

    def _should_overwrite(self, destination):
        if os.path.isfile(destination):
            if self.overwrite:
                self.lgr.debug('Overwriting: {0}'.format(destination))
            else:
                self.lgr.error('File already exists: {0}'.format(destination))
                sys.exit()

    def _handle_service_directory(self, init_system_file, create_directory):
        dirname = os.path.dirname(init_system_file)
        if not os.path.isdir(dirname):
            if create_directory:
                self.lgr.debug('Creating directory {0}...'.format(dirname))
                os.makedirs(dirname)
            else:
                self.lgr.error('Directory {0} does not exist and is required '
                               'for {1}. Terminating...'.format(
                                   dirname, init_system_file))
                sys.exit()

    def deploy_service_file(self, source, destination, create_directory=False):
        self._should_overwrite(destination)
        self.lgr.info('Deploying {0} to {1}...'.format(source, destination))
        self._handle_service_directory(destination, create_directory)
        shutil.move(source, destination)
