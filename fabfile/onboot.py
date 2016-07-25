from fabric.api import *
from fabric.api import settings


class FabricException(Exception):
    pass


@task
def start_dev_servers():
    shareabouts()
    api()


@task
def kill_dev_servers():
    with settings(abort_exception=FabricException):
        try:
            local("pkill -f '.*runserver.*'")
        except FabricException:
            pass


@task
def restart_dev_servers():
    kill_dev_servers()
    start_dev_servers()


def shareabouts():
    with lcd('/home/vagrant/shareabouts/src'):
        with prefix('. /home/vagrant/.virtualenvs/shareabouts/bin/activate'):
            local('./manage.py runserver 0.0.0.0:8000 &')


def api():
    with lcd('/home/vagrant/apicrowdspot/src'):
        with prefix('. /home/vagrant/.virtualenvs/apicrowdspot/bin/activate'):
            local('./manage.py runserver 0.0.0.0:8001 &')
