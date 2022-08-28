# Get4For6 – Debian deployment guide
This guide assumes you are running **Debian 11 Bullseye** (or a distribution derived from it, such as Raspberry Pi OS).




## I. Prerequisites
This guide assumes that the **Debian router** to which you are deploying has the following characteristics 
(you are, of course, free to make any changes):
- `lan0` is an IPv4-only LAN interface (in most cases, this will be a bridge)
- `wan0` is a dual-stack (i.e. with both IPv4 and IPv6 connectivity) WAN interface
- `get4for6` is a TUN interface created by the Tundra instance you are deploying
- The LAN is using the subnet `192.168.0.0/24`, and the router is using the IP address `192.168.0.1`
- The IPv6 prefix `2001:db8:dead:beef:cafe:4444:c0a8:0/120` is routed to the router's WAN interface
- You are going to be using the `100.100.0.0/22` substitute IPv4 subnet for translation
- Tundra is going to have the `192.168.46.0/24` IPv4 subnet and the `2001:db8:dead:beef:cafe:4646:0:0/112` IPv6 prefix
  for its own needs


  

## II. Preparations
1. Create a user account with limited privileges under which the deployed services will run:
   ```shell
   sudo adduser --shell=/bin/false --disabled-password --disabled-login get4for6
   sudo chmod 0700 /home/get4for6
   ```


2. Enable IPv4 and IPv6 forwarding by adding the following lines to `/etc/sysctl.conf`:
   ```text
   net.ipv4.ip_forward=1
   net.ipv6.conf.all.forwarding=1
   ```
   Apply the configuration changes by executing `sysctl -p`.


3. Set up the firewall & NAT to suit your needs:
   - The file [iptables.sh](iptables.sh) contains commands to set up basic `FORWARD` rules for both IPv4 and IPv6
     (it is STRONGLY RECOMMENDED to also define rules for the `INPUT` and `OUTPUT` chains according to your needs).
   - It is assumed that you do not mind exposing your private IPv4 addresses to the outside world; if you do (or you do 
     not have a IPv6 prefix routed to your router, but rather only a single IPv6 address), set up a `MASQUERADE` NAT 
     rule for IPv6, and adjust the other firewall rules to it.




## III. Cloning, building, installing dependencies
1. Clone the [Tundra-NAT64](https://github.com/vitlabuda/tundra-nat64) Git repository, build the program, and move
   the executable to `/usr/local/sbin/tundra-nat64`:
   ```shell
   git clone https://github.com/vitlabuda/tundra-nat64.git
   cd tundra-nat64
   
   gcc -Wall -Wextra -pthread -std=c11 -O3 -flto -o tundra-nat64 src/t64_*.c
   strip tundra-nat64
   
   sudo mv tundra-nat64 /usr/local/sbin/tundra-nat64
   sudo chown root:root /usr/local/sbin/tundra-nat64
   sudo chmod 0755 /usr/local/sbin/tundra-nat64
   ```

2. Under the `get4for6` user, and while in that user's home directory (this is important!), clone the 
   [Get4For6](https://github.com/vitlabuda/get4for6) Git repository:
   ```shell
   sudo su - get4for6 -s/bin/bash
   git clone https://github.com/vitlabuda/get4for6.git
   exit
   ```

3. Install the dependencies of Get4For6:
   ```shell
   sudo apt update
   sudo apt install python3 python3-pip python3-virtualenv virtualenv
   ```




## IV. Configuring the programs
1. Copy the [tundra.conf](tundra.conf), [start-tundra.sh](start-tundra.sh) and [stop-tundra.sh](stop-tundra.sh)
   files from [this directory](.) to the newly-created `/usr/local/etc/tundra-get4for6` directory (you may, of course, 
   make changes to them if you need to):
   ```shell
   sudo mkdir /usr/local/etc/tundra-get4for6
   sudo cp tundra.conf start-tundra.sh stop-tundra.sh /usr/local/etc/tundra-get4for6
   
   sudo chown root:root /usr/local/etc/tundra-get4for6/*
   sudo chmod 0644 /usr/local/etc/tundra-get4for6/*.conf
   sudo chmod 0755 /usr/local/etc/tundra-get4for6/*.sh
   ```

2. Copy the [get4for6.toml](get4for6.toml) configuration file from [this directory](.) to the newly-created
   `/usr/local/etc/get4for6` directory (you may, of course, make changes to it if you need to):
   ```shell
   sudo mkdir /usr/local/etc/get4for6
   sudo cp get4for6.toml /usr/local/etc/get4for6
   
   sudo chown root:root /usr/local/etc/get4for6/get4for6.toml
   sudo chmod 0644 /usr/local/etc/get4for6/get4for6.toml
   ```




## V. Setting up the services 
1. Copy the [get4for6.service](get4for6.service) and [tundra-get4for6.service](tundra-get4for6.service) unit files from 
   [this directory](.) to the `/etc/systemd/system` directory, and reload systemd:
   ```shell
   sudo cp get4for6.service tundra-get4for6.service /etc/systemd/system
   
   sudo chown root:root /etc/systemd/system/get4for6.service /etc/systemd/system/tundra-get4for6.service
   sudo chmod 0644 /etc/systemd/system/get4for6.service /etc/systemd/system/tundra-get4for6.service
   
   sudo systemctl daemon-reload
   ```


2. Start the newly-added services, and if everything works correctly, enable them, so they can start automatically on 
   boot:
   ```shell
   sudo systemctl start get4for6
   sudo systemctl start tundra-get4for6
   
   sudo systemctl enable get4for6
   sudo systemctl enable tundra-get4for6
   ```
