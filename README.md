# Installation and usage

## Get your local development environment working
1. You need to install virtualbox
1. You also need to install vagrant
1. Clone the github repository containing this README file:
`git clone git@github.com:CrowdSpot/crowdspot-vagrant-box.git ~/crowdspot-vagrant-box`
1. Obtain the virtualbox image (ubuntu 14.04 LTS) which contains the local development environment:
`cd ~/crowdspot-vagrant-box && wget <uri to s3 bucket>`
1. Clone the shareabouts repo locally (this will get synced into your virtual machine via the vagrant config):
`cd ~/crowdspot-vagrant-box`
`git clone git@github.com:CrowdSpot/shareabouts.git shareabouts`
4. Checkout the v3 branch (this is effectively master, as far as you guys are concerned):
`cd shareabouts && git checkout v3`
5. Start up the vagrant box and ssh to it:
`vagrant up` # Activate your virtualbox
`vagrant ssh` # Enter your virtualbox
  - `vagrant` as default password if prompted
6. Copy the local settings template to create a local settings file (this is done whilst ssh'd into the vagrant box):
`cp /home/vagrant/shareabouts/src/project/local_settings.py.template /home/vagrant/shareabouts/src/project/local_settings.py`
7. Restart the development servers on the vagrant box:
`fab -f ~/fabfile restart_dev_servers`
8. Access your local development environment:
Go to `http://127.0.0.1:8000/` in your browser and you are good to go :)

## Development workflow - developing a new flavour

1. On your local file system, checkout a new feature branch off v3 (let's for example's sake call it sekrit-project):
* `cd ~/crowdspot-vagrant-box/shareabouts`
* `git checkout v3`
* `git checkout -b feature-sekrit-project`
2. Create your new flavour, probably by copying an existing one and renaming the directory (again let's call it sekrit-project)
3. Update local_settings.py to point at your new flavour (eg, change contents so FLAVOUR=sekrit-project)
4. Restart the development servers on your virtualbox:
* `cd ~/crowdspot-vagrant-box && vagrant ssh`
* `fab -f ~/fabfile restart_dev_servers`
5. Access your local development environment to review your changes:
* Go to `http://127.0.0.1:8000/` and you are good to go :)
6. Commit and push your changes on your local file system:
* `cd ~/crowdspot-vagrant-box/shareabouts`
* `git commit -m"Created the sekrit-project flavour and tested"
* `git push origin feature-sekrit-project`

## Development workflow - reviewing your colleague's flavour

1. Checkout your colleague's feature branch (let's call it feature-sekrit-project) on your local filesystem:
* `cd ~/crowdspot-vagrant-box/shareabouts`
* `git fetch origin`
* `git checkout feature-sekrit-project`
2. Update local_settings.py to point at your new flavour (eg, change contents so FLAVOUR=sekrit-project)
4. Restart the development servers on your virtualbox:
* `cd ~/crowdspot-vagrant-box && vagrant ssh`
* `fab -f ~/fabfile restart_dev_servers`
5. Access your local development environment to review your colleague's changes:
* Go to `http://127.0.0.1:8000/` in your browser


# Background & Other Useful Information

## Superuser access
* username: crowdspot
* password: cc&20!6@

## ISO configuration
### Get repos

* apicrowdspot: tar/copied directly from the production server (though the repo is does exist at https://github.com/openplans/shareabouts-api)
* shareabouts:
** `git clone git@github.com:CrowdSpot/shareabouts.git`
** `cd shareabouts`
** `git checkout v3`

### Install guest additions

* `sudo apt-get install virtualbox-guest-additions-iso`
* `sudo mount /usr/share/virtualbox/VBoxGuestAdditions.iso /mnt`
* `cd /mnt`
* `sudo ./VBoxLinuxAdditions.run`

Note - need to run `vagrant reload` to include synced folders (also need uncomment synced_folders in vagrant file)

### Install PIP

* `sudo apt-get -y install python-pip`

### Install VirtualEnv/VirtualEnvWrapper

___Installation__
* `sudo pip install virtualenv`
* `sudo pip install virtualenvwrapper`

__Configuration__
* `echo 'export WORKON_HOME=$HOME/.virtualenvs'  >> .bashrc`
* `echo 'export PROJECT_HOME=$HOME/Devel'  >> .bashrc`
* `echo 'source /usr/local/bin/virtualenvwrapper.sh'  >> .bashrc`
* `source .bashrc`

### Install Pyenv - to handle different python versions

__Installation__
* `git clone git@github.com:yyuu/pyenv.git ~/.pyenv`
* `sudo apt-get install -y make build-essential libssl-dev zlib1g-dev `libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev libncursesw5-dev

__Configuration__
* `echo 'export PYENV_ROOT="$HOME/.pyenv"' >> .bashrc`
* `echo 'export PATH="$PYENV_ROOT/bin:$PATH"' >> .bashrc`
* `echo 'eval "$(pyenv init -)"' >> .bashrc`
* `exec $SHELL`

__Install Python Version__
* `pyenv install 2.7.3`

### Install Postgres\Postgis

__Installation__
* `sudo apt-get install -y postgresql postgresql-contrib`
* `sudo apt-get install -y postgis postgresql-9.3-postgis-2.1`
* `sudo apt-get install libpq-dev python-dev`

__Create Database__
* `sudo -u postgres createuser -Ps vagrant`
* Add your password
* `createuser -P shareabouts`
* `createdb -O shareabouts shareabouts`
* Check if you could access your database - `psql -h localhost -U shareabouts shareabouts`
* `psql -c "CREATE EXTENSION postgis; CREATE EXTENSION postgis_topology;" shareabouts`

### Create VirtualEnv, Install python dependencies, Start dev server

#### shareabouts (vanilla instance which uses the default flavour)

__Installation__
* `mkvirtualenv /home/vagrant/.virtualenvs/shareabouts`
* `cd /home/vagrant/shareabouts`
* `workon shareabouts`
* `pip install -Ur snapshotted_requirements.txt`

__Create local settings file__
* `cp /home/vagrant/shareabouts/src/project/local_settings.py.template /home/vagrant/shareabouts/src/project/local_settings.py`

__Start Dev Server__
* `cd src`
* `./manage.py runserver 0.0.0.0:8000`

#### Apicrowdspot

__Installation__
* `mkvirtualenv -p ~/.pyenv/versions/2.7.3/bin/python2.7 apicrowdspot`
* `cd home/vagrant/apicrowdspot`
* `pip install -Ur requirements.txt`

__database__
* `./manage.py syncdb --migrate`
* `./manage.py createsuperuser`
    * username: crowdspot
    * email: just press enter
    * password: cc&20!6@

__Start Dev Server__
* `cd src`
* `./manage.py runserver 0.0.0.0:8001`

__Configure Api__
* Go to `http://127.0.0.1:8001/admin/` in your browser
    * username: `crowdspot`
    * password: `cc&20!6@`

* Go to API Keys
    * Add API Key: `MGJlYzRhMTIxNGFkNDYyMmU1ZDRmNmNk`
    * Add Dataset
        * owner: `crowdspot`
        * display name: `default-instance`
        * save Dataset
    * save API Keys

* Go to `http://127.0.0.1:8000/` and you are good to go :)
