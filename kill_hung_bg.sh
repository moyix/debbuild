#!/bin/bash

while true; do
  ps -e -o pid,etimes,comm,cmd | grep -E '(erl_child_setup|xvfb-run)' | \
    grep -Ev '(Xvfb|wrapper|grep)' | awk '$2 > 30' | \
    while read -r pid etime comm cmd; do 
      echo "Killing $pid ($comm) which has been running for $etime seconds: ${cmd}"
      killbutmakeitlooklikeanaccident.sh "$pid"
    done
  ps -e -o pid,ppid,etimes,comm,cmd | grep '\borted\b' | grep -v wrapper | awk '$3 > 30' | \
    while read -r pid ppid etime comm cmd ; do
      gpid=$(ps -e -o pid,ppid | awk '$1 == '"${ppid}"' { print $2 }')
      gpcmd=$(ps -e -o pid,cmd | awk '$1 == '"${gpid}"' { $1=""; print }')
      echo "Killing grandparent of $pid ($comm) which has been running for $etime seconds: [${gpid}] ${gpcmd}"
      killbutmakeitlooklikeanaccident.sh "$gpid"
    done
  sleep 1
done
