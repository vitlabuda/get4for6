#!/bin/bash

if [ -z "${MAINPID}" ]; then
	echo 'The MAINPID environment variable is not present!'
	exit 1
fi

TUNDRA_EXECUTABLE="/usr/local/sbin/tundra-nat64"
TUNDRA_CONFIG_FILE="/usr/local/etc/tundra-get4for6/tundra.conf"


/bin/kill -TERM "${MAINPID}" || exit 1

while [ -e "/proc/${MAINPID}" ]; do
	/bin/sleep 0.25 || exit 1
done

${TUNDRA_EXECUTABLE} --config-file="${TUNDRA_CONFIG_FILE}" rmtun || exit 1
