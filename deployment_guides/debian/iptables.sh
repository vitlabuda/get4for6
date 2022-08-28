#!/bin/bash



##### IPv4 #####
iptables -A FORWARD -m conntrack --ctstate INVALID -j DROP
iptables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

iptables -A FORWARD -i lan0 -o lan0 -j ACCEPT  # Allow LAN hosts to communicate with each other
iptables -A FORWARD -s 192.168.0.0/24 -i lan0 -o wan0 -j ACCEPT  # Allow native IPv4 connectivity to the Internet
iptables -A FORWARD -s 192.168.0.0/24 -d 100.100.0.0/22 -i lan0 -o get4for6 -j ACCEPT  # Allow to-be-translated packets to enter the NAT46 translator

# If you want LAN hosts to be accessible from the IPv6 Internet via the NAT46 translator, uncomment the following lines
#iptables -A FORWARD -s 100.100.0.0/22 -d 192.168.0.0/32 -i get4for6 -o lan0 -j DROP  # Drop packets destined towards the LAN's network address
#iptables -A FORWARD -s 100.100.0.0/22 -d 192.168.0.1/32 -i get4for6 -o lan0 -j DROP  # Drop packets destined towards the router
#iptables -A FORWARD -s 100.100.0.0/22 -d 192.168.0.255/32 -i get4for6 -o lan0 -j DROP  # Drop packets destined towards the LAN's broadcast address
#iptables -A FORWARD -s 100.100.0.0/22 -d 192.168.0.0/24 -i get4for6 -o lan0 -j ACCEPT  # Accept packets destined towards LAN hosts

iptables -t nat -A POSTROUTING -o wan0 -j MASQUERADE   # Masquerade addresses of IPv4 packets going to the WAN



##### IPv6 #####
ip6tables -A FORWARD -m conntrack --ctstate INVALID -j DROP
ip6tables -A FORWARD -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT

ip6tables -A FORWARD -i lan0 -o lan0 -j ACCEPT  # Allow LAN hosts to communicate with each other
ip6tables -A FORWARD -s 2001:db8:dead:beef:cafe:4444:c0a8:0/120 -i get4for6 -o wan0 -j ACCEPT  # Allow NAT46-translated packets to go to the Internet

# If you want LAN hosts to be accessible from the IPv6 Internet via the NAT46 translator, uncomment the following lines
#ip6tables -A FORWARD -d 2001:db8:dead:beef:cafe:4444:c0a8:0/128 -i wan0 -o get4for6 -j DROP  # Drop packets destined towards the LAN's network address
#ip6tables -A FORWARD -d 2001:db8:dead:beef:cafe:4444:c0a8:1/128 -i wan0 -o get4for6 -j DROP  # Drop packets destined towards the router
#ip6tables -A FORWARD -d 2001:db8:dead:beef:cafe:4444:c0a8:ff/128 -i wan0 -o get4for6 -j DROP  # Drop packets destined towards the LAN's broadcast address
#ip6tables -A FORWARD -d 2001:db8:dead:beef:cafe:4444:c0a8:0/120 -i wan0 -o get4for6 -j ACCEPT  # Accept packets destined towards LAN hosts
