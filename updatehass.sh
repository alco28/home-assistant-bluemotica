#!/bin/bash

HA_USER="homeassistant"
HA_USERROOT="/home/$HA_USER"
HA_SRVROOT="/srv/homeassistant"
HA_PYENV_ACTIVATION="export PATH=\"$HA_USERROOT/.pyenv/bin:\$PATH\"; export PYENV_VIRTUALENV_DISABLE_PROMPT=1; eval \"\$(pyenv init -)\"; eval \"\$(pyenv virtualenv-init -)\""
HA_PYTHON_VERSION="3.6.3"

echo "Stopping HA..."
systemctl stop home-assistant.service

echo "Updating HA"
su --shell /bin/bash --command "cd $HA_SRVROOT; $HA_PYENV_ACTIVATION; pyenv activate homeassistant-$HA_PYTHON_VERSION; pip3 install --upgrade homeassistant" $HA_USER

echo "Starting HA..."
systemctl start home-assistant.service

echo "Checking to see if up (Localhost must be in http trusted_networks)"
start=$(date '+%s')

until curl --silent --show-error --connect-timeout 1 -X GET -H "Content-Type: application/json" -k https://127.0.0.1:8123/api/ | grep -q 'API running'; do
    date '+[%Y-%m-%d %H:%M:%S] --- Home Assistant is starting, please wait...'
    systemctl status home-assistant.service
    sleep 10
done

dur=$(($(date '+%s') - start))

echo -e "\e[00;32mHome Assistant is ready! ($dur second delay)\e[00m"
