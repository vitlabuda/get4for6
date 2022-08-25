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
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc


class _StaticSubstituteAddressMapper:
    """
    Maps statically assigned substitute IPv4 addresses to IPv6 addresses, and vice versa.
    """

    # Even short-term caching improves performance greatly, and is far less prone to problems than caching for longer
    #  periods of time.
    _EXTERNAL_CACHE_LIFETIME: Final[int] = 15

    def __init__(self, static_assignments: tuple[tuple[ipaddress.IPv4Address, ipaddress.IPv6Address], ...]):
        """
        It is assumed that the supplied arguments are valid. Under normal circumstances, the necessary validity checks
         are carried out by this program's configuration loading procedures.
        """

        self._static_map_4to6: Final[dict[ipaddress.IPv4Address, ipaddress.IPv6Address]] = dict()
        self._static_map_6to4: Final[dict[ipaddress.IPv6Address, ipaddress.IPv4Address]] = dict()

        for ipv4_address, ipv6_address in static_assignments:
            self._static_map_4to6[ipv4_address] = ipv6_address
            self._static_map_6to4[ipv6_address] = ipv4_address

    def get_external_cache_lifetime(self) -> int:
        return self.__class__._EXTERNAL_CACHE_LIFETIME

    def find_substitute_assignment_4to6(self, ipv4_address: ipaddress.IPv4Address) -> ipaddress.IPv6Address:
        """
        :raises SubstituteAssignmentNotFoundExc
        """

        assert isinstance(ipv4_address, ipaddress.IPv4Address)  # Make sure that nothing is broken (and nothing will break)

        try:
            return self._static_map_4to6[ipv4_address]
        except KeyError:
            raise SubstituteAssignmentNotFoundExc(ipv4_address)

    def find_substitute_assignment_6to4(self, ipv6_address: ipaddress.IPv6Address) -> ipaddress.IPv4Address:
        """
        :raises SubstituteAssignmentNotFoundExc
        """

        assert isinstance(ipv6_address, ipaddress.IPv6Address)  # Make sure that nothing is broken (and nothing will break)

        try:
            return self._static_map_6to4[ipv6_address]
        except KeyError:
            raise SubstituteAssignmentNotFoundExc(ipv6_address)
