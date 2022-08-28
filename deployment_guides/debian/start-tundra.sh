#!/bin/bash

TUNDRA_EXECUTABLE="/usr/local/sbin/tundra-nat64"
TUNDRA_CONFIG_FILE="/usr/local/etc/tundra-get4for6/tundra.conf"
TUNDRA_INTERFACE="get4for6"


${TUNDRA_EXECUTABLE} --config-file="${TUNDRA_CONFIG_FILE}" mktun || exit 1

/bin/ip link set dev "${TUNDRA_INTERFACE}" up || exit 1
/bin/ip -4 addr add '192.168.46.254/24' dev "${TUNDRA_INTERFACE}" || exit 1
/bin/ip -6 addr add '2001:db8:dead:beef:cafe:4646:0:fffe/112' dev "${TUNDRA_INTERFACE}" || exit 1
/bin/ip -4 route add '100.100.0.0/22' dev "${TUNDRA_INTERFACE}" || exit 1
/bin/ip -6 route add '2001:db8:dead:beef:cafe:4444:0:0/96' dev "${TUNDRA_INTERFACE}" || exit 1

exec ${TUNDRA_EXECUTABLE} --config-file="${TUNDRA_CONFIG_FILE}" translate
