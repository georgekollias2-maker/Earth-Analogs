#!/usr/bin/env bash
# Ξεκινά το demo από τον σωστό φάκελο, με ενεργό το static serving (για την υδρόγειο)
cd "$(dirname "$0")"
[ -f .venv/bin/activate ] && source .venv/bin/activate
python -m streamlit run app.py --server.enableStaticServing true
