#!/bin/bash


dir=$(pwd)

if ! $(python -c 'import yaml;import paramiko;import jinja2'); then
    echo "[pip] install rpm packages..."
    yum localinstall -y ansible/deps/pythonpip/*.rpm &> /dev/null
    echo "[pip] install rpm packages success"
    echo "[pip] install pip packages..."
    pip install ansible/deps/pythonpip/deps/* &> /dev/null
    echo "[pip] install pip packages success"
else
    echo "[pip] pip dependencies detected, skip"
fi

if ! [ -x "$(command -v ansible-playbook)" ]; then
    echo "[ansible] source ansible env..."
    source ansible/hacking/env-setup
    echo "[ansible] source ansible env success"
else
    echo "[ansible] ansible-playbook detected, skip"
fi
