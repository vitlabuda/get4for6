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


from typing import Final
import ipaddress
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.addr_mapper.client.exc.ClientIPv4AddressNotAllowedExc import ClientIPv4AddressNotAllowedExc
from get4for6.addr_mapper.client.exc.ClientIPv6PrefixIncorrectExc import ClientIPv6PrefixIncorrectExc
from get4for6.addr_mapper.client.exc.ClientIPv6ContainsScopeIDExc import ClientIPv6ContainsScopeIDExc


class ClientAddressMapper:
    """
    Statelessly maps allowed IPv4 addresses (belonging to clients) into an /96 IPv6 prefix, and vice versa.
    """

    def __init__(self, client_allowed_subnets: tuple[ipaddress.IPv4Network, ...], map_client_addrs_into: ipaddress.IPv6Network):
        """
        It is assumed that the supplied arguments are valid. Under normal circumstances, the necessary validity checks
         are carried out by this program's configuration loading procedures.
        """

        assert (map_client_addrs_into.prefixlen == 96)

        self._client_allowed_subnets: Final[tuple[ipaddress.IPv4Network, ...]] = client_allowed_subnets
        self._map_client_addrs_into_binary_prefix: Final[bytes] = map_client_addrs_into.network_address.packed[0:12]

    def map_client_4to6(self, ipv4_address: ipaddress.IPv4Address) -> ipaddress.IPv6Address:
        """
        :raises ClientIPv4AddressNotAllowedExc
        """

        assert isinstance(ipv4_address, ipaddress.IPv4Address)  # Make sure that nothing is broken (and nothing will break)

        self._check_if_ipv4_address_is_allowed(ipv4_address)

        return ipaddress.IPv6Address(self._map_client_addrs_into_binary_prefix + ipv4_address.packed)

    def map_client_6to4(self, ipv6_address: ipaddress.IPv6Address) -> ipaddress.IPv4Address:
        """
        :raises ClientIPv6PrefixIncorrectExc
        :raises ClientIPv4AddressNotAllowedExc
        :raises ClientIPv6ContainsScopeIDExc
        """

        assert isinstance(ipv6_address, ipaddress.IPv6Address)  # Make sure that nothing is broken (and nothing will break)

        if ipv6_address.scope_id is not None:
            raise ClientIPv6ContainsScopeIDExc(ipv6_address)

        binary_ipv6 = ipv6_address.packed

        self._check_if_ipv6_prefix_is_correct(binary_ipv6[0:12])

        ipv4_address = ipaddress.IPv4Address(binary_ipv6[12:16])
        self._check_if_ipv4_address_is_allowed(ipv4_address)
        return ipv4_address

    def _check_if_ipv4_address_is_allowed(self, ipv4_address: ipaddress.IPv4Address) -> None:
        if not IPHelpers.is_ipv4_address_part_of_any_subnet(ipv4_address, self._client_allowed_subnets):
            raise ClientIPv4AddressNotAllowedExc(ipv4_address)

    def _check_if_ipv6_prefix_is_correct(self, binary_ipv6_prefix: bytes) -> None:
        assert (len(binary_ipv6_prefix) == 12)

        if binary_ipv6_prefix == self._map_client_addrs_into_binary_prefix:
            return

        ipv6_prefix_network_address = ipaddress.IPv6Address(binary_ipv6_prefix + (b'\x00' * 4))
        ipv6_prefix = ipaddress.IPv6Network((ipv6_prefix_network_address, 96))
        raise ClientIPv6PrefixIncorrectExc(ipv6_prefix)
