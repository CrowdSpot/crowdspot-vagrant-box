# -*- mode: ruby; -*-
require 'etc'

Vagrant.configure("2") do |config|
  config.vm.box = "crowdspot.box"
  config.vm.box_url = "crowdspot.box"
  config.vm.synced_folder "apicrowdspot/", "/home/vagrant/apicrowdspot"
  config.vm.synced_folder "shareabouts/", "/home/vagrant/shareabouts"
  config.vm.define :web do |web|

    # Network
    web.vm.hostname = "dev"

    # Port forwards
    web.vm.network :forwarded_port, guest: 8000,  host: 8000  ,  auto_correct: true     # Django UI - dev server
    web.vm.network :forwarded_port, guest: 8001,  host: 8001,  auto_correct: true     # Django UI - dev server

    # Customize the box
    web.vm.provider :virtualbox do |v|
      v.customize ["modifyvm", :id, "--memory", 4096]
      v.cpus = 4
    end
  config.ssh.forward_agent = true
  end
end
