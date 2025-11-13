#!/usr/bin/bash

export PYTHONPATH=/home/pos/kirsa-kkm
cd /home/pos/kirsa-kkmpos
env/bin/python3 main.py --uds=kirsa-kkmpos.sock

