#!/bin/false

# Copyright (c) 2022 Vít Labuda. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted provided that the
# following conditions are met:
#  1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following
#     disclaimer.
#  2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the
#     following disclaimer in the documentation and/or other materials provided with the distribution.
#  3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote
#     products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
# INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from typing import Sequence, Optional
import ipaddress
from get4for6.config.Configuration import Configuration
from get4for6.etc.UninstantiableClassMixin import UninstantiableClassMixin


# This is not really a class as per OOP definition, but rather a collection of independent functions.
class IPHelpers(UninstantiableClassMixin):
    # One of the things that could be improved on this program design-wise is the validation of IP addresses - as of
    #  now, there is no abstraction to provide this functionality (the only thing to be somehow close to it is this
    #  pseudo-class).
    # There are reasons why this has not been done (the configuration is parsed using 'datalidator', which validates
    #  IP addresses differently from the rest of the program), but when this program was finished, it turned out that
    #  because of this, its maintainability took a big hit.
    # Although everything seems to be working as intended at the moment, if the program was to be refactored, this is
    #  one of the improvements one should certainly focus on.

    @staticmethod
    def is_ipv6_address_substitutable(address: ipaddress.IPv6Address) -> bool:
        return bool((not address.is_unspecified) and (not address.is_loopback) and (not address.is_multicast) and (address.scope_id is None))

    @staticmethod
    def is_ipv4_address_the_network_or_broadcast_address_of_subnet(address: ipaddress.IPv4Address, subnet: ipaddress.IPv4Network) -> bool:
        return bool((subnet.prefixlen <= 30) and ((address == subnet.network_address) or (address == subnet.broadcast_address)))

    @classmethod
    def is_ipv4_address_part_of_any_subnet(cls, address: ipaddress.IPv4Address, subnets: Sequence[ipaddress.IPv4Network]) -> bool:
        """
        This method also returns 'False' if the address is the network or the broadcast address of a subnet.
        """

        for subnet in subnets:
            if address in subnet:
                if cls.is_ipv4_address_the_network_or_broadcast_address_of_subnet(address, subnet):
                    return False
                return True

        return False

    @staticmethod
    def is_ipv4_address_part_of_any_subnet_loose(address: ipaddress.IPv4Address, subnets: Sequence[ipaddress.IPv4Network]) -> bool:
        for subnet in subnets:
            if address in subnet:
                return True

        return False

    @classmethod  # In helpers, the dependency injector is not used, as it might not be ready yet
    def parse_client_ipv4_from_string_and_validate_it(cls, ip_string: str, configuration: Configuration) -> Optional[ipaddress.IPv4Address]:
        try:
            client_ipv4 = ipaddress.IPv4Address(ip_string)
        except ValueError:
            return None

        if not cls.is_ipv4_address_part_of_any_subnet(client_ipv4, configuration.translation.client_allowed_subnets):
            return None

        return client_ipv4
