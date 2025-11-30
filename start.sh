#!/usr/bin/bash

export PYTHONPATH=~/kirsa-kkm
cd ~/kirsa-kkmpos
env/bin/python3 main.py --uds=kirsa-kkmpos.sock

