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


from typing import Final, Optional, Union, Generator
import ipaddress
from get4for6.config.DynamicSubstituteAddrAssigningOptions import DynamicSubstituteAddrAssigningOptions
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.exc.ThisShouldNeverHappenExc import ThisShouldNeverHappenExc
from get4for6.addr_mapper.substitute._StaticSubstituteAddressMapper import _StaticSubstituteAddressMapper
from get4for6.addr_mapper.substitute._DynamicSubstituteAddressMapper import _DynamicSubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.IPv6AddressNotSubstitutableExc import IPv6AddressNotSubstitutableExc
from get4for6.addr_mapper.substitute.exc.SubstituteIPv4AddressNotAllowedExc import SubstituteIPv4AddressNotAllowedExc


class SubstituteAddressMapper:
    """
    Statefully maps substitute IPv4 addresses to IPv6 addresses, and vice versa, by managing and using an instance of
     static mapper and, if desired, per-client instances of dynamic mappers.
    """

    def __init__(self, client_allowed_subnets: tuple[ipaddress.IPv4Network, ...], substitute_subnets: tuple[ipaddress.IPv4Network, ...], static_substitute_addr_assignments: tuple[tuple[ipaddress.IPv4Address, ipaddress.IPv6Address], ...], dynamic_substitute_addr_assigning: Optional[DynamicSubstituteAddrAssigningOptions]):
        """
        It is assumed that the supplied arguments are valid. Under normal circumstances, the necessary validity checks
         are carried out by this program's configuration loading procedures.
        """

        self._client_allowed_subnets: Final[tuple[ipaddress.IPv4Network, ...]] = client_allowed_subnets
        self._substitute_subnets: Final[tuple[ipaddress.IPv4Network, ...]] = substitute_subnets
        self._dynamic_substitute_addr_assigning: Final[Optional[DynamicSubstituteAddrAssigningOptions]] = dynamic_substitute_addr_assigning

        self._do_not_assign_dynamically: Final[frozenset[ipaddress.IPv4Address]] = frozenset({ipv4_address for ipv4_address, _ in static_substitute_addr_assignments})
        self._static_mapper: Final[_StaticSubstituteAddressMapper] = _StaticSubstituteAddressMapper(static_assignments=static_substitute_addr_assignments)
        self._per_client_dynamic_mappers: Final[dict[ipaddress.IPv4Address, _DynamicSubstituteAddressMapper]] = dict()

    def map_substitute_4to6(self, ipv4_address: ipaddress.IPv4Address, valid_client_ipv4: ipaddress.IPv4Address) -> tuple[ipaddress.IPv6Address, int]:  # (IPv6 address, external cache lifetime)
        """
        :raises SubstituteAssignmentNotFoundExc
        :raises SubstituteIPv4AddressNotAllowedExc
        """

        assert isinstance(ipv4_address, ipaddress.IPv4Address)  # Make sure that nothing is broken (and nothing will break)
        assert isinstance(valid_client_ipv4, ipaddress.IPv4Address)

        self._perform_fallback_check_of_client_ipv4_validity(valid_client_ipv4)

        if not IPHelpers.is_ipv4_address_part_of_any_subnet(ipv4_address, self._substitute_subnets):
            raise SubstituteIPv4AddressNotAllowedExc(ipv4_address)

        try:
            return self._static_mapper.find_substitute_assignment_4to6(ipv4_address), self._static_mapper.get_external_cache_lifetime()
        except SubstituteAssignmentNotFoundExc:
            pass

        # If dynamic address mapping is disabled, 'SubstituteAssignmentNotFoundExc' will be raised
        dynamic_mapper = self._find_dynamic_mapper_for_client(ipv4_address, valid_client_ipv4)

        return dynamic_mapper.find_substitute_assignment_4to6(ipv4_address), dynamic_mapper.get_external_cache_lifetime()

    def map_substitute_6to4(self, ipv6_address: ipaddress.IPv6Address, valid_client_ipv4: ipaddress.IPv4Address, mapping_creation_allowed: bool) -> tuple[ipaddress.IPv4Address, int]:  # (IPv4 address, external cache lifetime)
        """
        :raises SubstituteAssignmentNotFoundExc
        :raises IPv6AddressNotSubstitutableExc
        :raises SubstituteAddressSpaceCurrentlyFullExc
        """

        assert isinstance(ipv6_address, ipaddress.IPv6Address)  # Make sure that nothing is broken (and nothing will break)
        assert isinstance(valid_client_ipv4, ipaddress.IPv4Address)

        self._perform_fallback_check_of_client_ipv4_validity(valid_client_ipv4)

        if not IPHelpers.is_ipv6_address_substitutable(ipv6_address):
            raise IPv6AddressNotSubstitutableExc(ipv6_address)

        try:
            return self._static_mapper.find_substitute_assignment_6to4(ipv6_address), self._static_mapper.get_external_cache_lifetime()
        except SubstituteAssignmentNotFoundExc:
            pass

        # If dynamic address mapping is disabled, 'SubstituteAssignmentNotFoundExc' will be raised
        dynamic_mapper = self._find_dynamic_mapper_for_client(ipv6_address, valid_client_ipv4)

        return dynamic_mapper.find_or_create_substitute_assignment_6to4(ipv6_address, mapping_creation_allowed), dynamic_mapper.get_external_cache_lifetime()

    def _perform_fallback_check_of_client_ipv4_validity(self, valid_client_ipv4: ipaddress.IPv4Address) -> None:
        # Components calling this mapper MUST ensure that the client IPv4 address they are passing here is allowed.
        #  This check is entirely last-resort, because we want to make absolutely sure that a dynamic mapper cannot be
        #  allocated to an unauthorized client.

        if not IPHelpers.is_ipv4_address_part_of_any_subnet(valid_client_ipv4, self._client_allowed_subnets):
            raise ThisShouldNeverHappenExc(f"The provided client IPv4 address ({valid_client_ipv4}) should have already been validated!")

    def _find_dynamic_mapper_for_client(self, mapped_ip_address: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], valid_client_ipv4: ipaddress.IPv4Address) -> _DynamicSubstituteAddressMapper:
        if self._dynamic_substitute_addr_assigning is None:  # Dynamic mappers are not available
            raise SubstituteAssignmentNotFoundExc(mapped_ip_address)

        try:
            return self._per_client_dynamic_mappers[valid_client_ipv4]
        except KeyError:
            pass

        new_dynamic_mapper = _DynamicSubstituteAddressMapper(
            substitute_subnets=self._substitute_subnets,
            do_not_assign=self._do_not_assign_dynamically,
            min_lifetime_after_last_hit=self._dynamic_substitute_addr_assigning.min_lifetime_after_last_hit
        )
        self._per_client_dynamic_mappers[valid_client_ipv4] = new_dynamic_mapper
        return new_dynamic_mapper

    def send_dynamic_mappings_to_generator(self, generator: Generator[None, tuple[ipaddress.IPv4Address, ipaddress.IPv4Address, ipaddress.IPv6Address, int], None]) -> None:
        for client_ipv4, dynamic_mapper in self._per_client_dynamic_mappers.items():
            dynamic_mapper.send_dynamic_mappings_to_generator(generator, client_ipv4)
