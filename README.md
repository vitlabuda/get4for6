<!--
Copyright (c) 2022 Vít Labuda. All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
following conditions are met:
 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
    disclaimer.
 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
    following disclaimer in the documentation and/or other materials provided with the distribution.
 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
    products derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
-->

# Get4For6
**Get4For6** is an open-source **NAT46 and DNS46** translator for Linux, implemented in the form of an
[external address translator](https://github.com/vitlabuda/tundra-nat64/blob/main/external_addr_xlat/EXTERNAL-ADDR-XLAT-PROTOCOL.md)
for the [Tundra](https://github.com/vitlabuda/tundra-nat64) SIIT (RFC 7915) packet translator.

Its main purpose is to enable internal IPv4-only hosts to communicate with IPv6-only Internet hosts by providing a 
DNS forwarder/resolver which manipulates DNS queries and answers from the internal IPv4-only hosts. However, since the
translation model is designed in a way which does not break end-to-end connectivity, even IPv6-originated 
communication with IPv4 hosts is possible.

This program has been named `Get4For6`, as the way it provides IPv4-only hosts with connectivity to IPv6-only hosts is
by assigning each IPv6 address a substitute IPv4 address (either statically or dynamically), as is described below in 
this document.





## Functional & architectural overview
This program's design is centered around a **dependency injector** (the [sidein](https://github.com/vitlabuda/sidein)
framework has been used), which houses, among other things (like [configuration](src/get4for6/config)), the 
[client](src/get4for6/addr_mapper/client) address mapper and the [substitute](src/get4for6/addr_mapper/substitute) 
address mapper, and several **modules** – [`tundra_external_addr_xlat`](src/get4for6/modules/m_xax), 
[`dns`](src/get4for6/modules/m_dns) and [`simple_addr_query`](src/get4for6/modules/m_saq), which run independently 
of each other, listen for clients' requests on sockets and carry them out with the help of the aforementioned IP 
address mappers. To achieve concurrency, this program makes use of the `asyncio` library.



### Clients and their IP addresses
This program and its documentation use the term _clients_ for IPv4-only nodes which make use of this translator to
access resources available in IPv6-only Internet and/or other reachable networks. 

When packets are translated between IPv4 and IPv6, the address translator has a /96 IPv6 prefix configured, into 
which (4to6) and from which (6to4) it maps clients' IP addresses in a stateless, one-to-one manner – for example, if 
the prefix is configured to be `2001:db8:4444::/96` and a client's address is `192.168.0.1`, it will be translated to 
`2001:db8:4444::c0a8:1` = `2001:db8:4444::192.168.0.1`.

This approach to address translation is very simple, easily debuggable and makes it trivial to target a certain IPv4
client in case communication is initiated from IPv6. If you are worried about exposing private IPv4 addresses
used in your network(s) to the IPv6 outside world, you might consider using Linux's in-kernel NAT66 translator to 
`MASQUERADE` them.

The mapping of client addresses is facilitated by 
[`ClientAddressMapper`](src/get4for6/addr_mapper/client/ClientAddressMapper.py). 
See [the relevant parts of the example configuration file](get4for6.example.toml#L21-L43) for details.



### Substitute IPv4 addresses
This program and its documentation use the term _substitute addresses_ for IPv4 addresses to which IPv6 addresses
of IPv6-only Internet hosts are mapped in a one-to-one manner, either statically or dynamically. Each
client-originated IPv4 packet destined towards a substitute address will be translated into an IPv6 packet destined
towards the IPv6 address substituted by the substitute address, and a client-destined IPv6 packet originating from an
unicast IPv6 address will be translated into an IPv4 packet originating from the substitute address which
substitutes the unicast IPv6 address.

Configuration-specified **static substitute address assignments** are shared among all clients, whereas **dynamic
substitute address assignments** are created and then managed on a per-client basis – each client has its own dynamic 
mapping pool, and clients are not able to affect each other's mappings. Clients are distinguished from each other by 
their IPv4 addresses, meaning that all of this translator's services must be accessed from the same IP (e.g. DNS 
queries must have the same source IPv4 address as translated packets). 

The mapping of substitute addresses is facilitated by
[`SubstituteAddressMapper`](src/get4for6/addr_mapper/substitute/SubstituteAddressMapper.py).
See [the relevant parts of the example configuration file](get4for6.example.toml#L47-L116) for details.



### Tundra External Address Translation
Get4For6 is not a packet translator, but rather only an address translator. Therefore, in order for the NAT46/DNS46
translation to work as a whole, [Tundra](https://github.com/vitlabuda/tundra-nat64) in the external address
translation mode must be used. In this mode, Tundra, a fast C-written SIIT (RFC 7915) packet translator, translates
IPv4 packets to IPv6 and vice versa, and asks an external server program (such as this one) for IP addresses to be put 
in the translated packets, optionally caching them to reduce the external server's load. This enables address 
translators (such as this one) to be complex and written in slower, higher-level programming languages.

In [the `tundra_external_addr_xlat` section of the configuration file](get4for6.example.toml#L140-L158), there are 
options that specify on which Unix and/or TCP sockets Get4For6 will listen, and to which one or more Tundra instances 
(which may even run on remote machines) will connect, and then ask for addresses to be translated.



### DNS
The main purpose of this translator's DNS module is to make it possible for DNS-enabled IPv4-only clients to access
IPv6-only services without them needing to have any special software or configuration (the only requirement for
clients is to have this translator set as their recursive DNS server, which can be automated using DHCP).

The DNS module features a DNS forwarder (whose upstream servers are specified in the configuration file), which
synthesizes `A` (i.e. IPv4) records for domain names which have only `AAAA` (i.e. IPv6) records by using the 
above-described substitute IPv4 addresses (= **DNS46**), provides reverse `PTR` records for those addresses, enables 
clients to access IPv6 hosts which do not have a (known) domain name (but whose IPv6 address is known) using the 
integrated _auxiliary names_ functionality, and more.

See [the `dns` section of the example configuration file](get4for6.example.toml#L165-L190) for a detailed explanation 
of how the DNS server provided by this translator operates, and how to configure it.



### Simple Address Query
`simple_addr_query` is an extremely simple UDP-based protocol, which allows IPv4 clients not supporting DNS or not 
willing to use it (e.g. programmable microcontrollers with very limited system resources) to make use of this 
translator's services, and thus access IPv6-only hosts.

Since it is assumed that this protocol will be rarely ever used, it is configured to be disabled by default.
See [the `simple_addr_query` section of the example configuration file](get4for6.example.toml#L269-L294) for details 
on how the protocol works, and how to configure its server.





## Configuration & deployment

### Generic information

#### The example configuration file
Before you start configuring the program by editing the [example configuration file](get4for6.example.toml), it is
strongly recommended to read all the comments in that file, since they provide important information on how this 
program and its components function **in thorough detail**, and how to configure them the best for your use case.
Furthermore, the [_security considerations_ comment](get4for6.example.toml#L118-L134) in that file contains tips on how 
to make this translator's deployments more secure.

#### Dependencies
Before starting the program, install the necessary dependencies:
- Using `apt` (Debian, Ubuntu etc.):
  ```shell
  sudo apt update
  sudo apt install python3 python3-pip python3-virtualenv virtualenv
  ```
- Using `dnf` (Fedora, CentOS, RHEL etc.):
  ```shell
  sudo dnf install python3 python3-pip python3-virtualenv virtualenv
  ```

#### Starting the program
To start the program, run the [`run_get4for6.sh`](src/run_get4for6.sh) shell script – pass the path of your 
configuration file to it through the first argument. The script will take care of initializing a Python virtual
environment with the necessary packages (see [requirements.txt](src/requirements.txt)).

#### Stopping the program
To stop a running Get4For6 instance, send the `SIGTERM`, `SIGINT` or `SIGHUP` signal to it.



### Specific deployment examples 
**Coming soon!**





## Licensing
This project is licensed under the **3-clause BSD license** – see the [LICENSE](LICENSE) file.

In addition, this project uses some third-party open-source components – see the 
[THIRD-PARTY-LICENSES](THIRD-PARTY-LICENSES) file.

Programmed by **[Vít Labuda](https://vitlabuda.cz/)**.
