#! /usr/bin/env bash

set -e
set -x

# Run all pre-start tasks (DB check, migrations, seeding)
python app/backend_pre_start.py

