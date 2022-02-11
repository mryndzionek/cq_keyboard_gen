#!/bin/bash

inotifywait -m output -e create |
    while read directory action file; do
        echo "Detected $file"
        if [[ "$file" == "atreus_52hs_cnc.step" ]]; then
            echo "last file detected"
            exit 0
        fi
    done
