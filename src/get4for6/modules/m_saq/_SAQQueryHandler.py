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


from typing import Optional, Union
import ipaddress
from get4for6.di import DI_NS
from get4for6.exc.ThisShouldNeverHappenExc import ThisShouldNeverHappenExc
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.SubstituteIPv4AddressNotAllowedExc import SubstituteIPv4AddressNotAllowedExc
from get4for6.addr_mapper.substitute.exc.IPv6AddressNotSubstitutableExc import IPv6AddressNotSubstitutableExc
from get4for6.addr_mapper.substitute.exc.SubstituteAddressSpaceCurrentlyFullExc import SubstituteAddressSpaceCurrentlyFullExc


class _SAQQueryHandler:
    @DI_NS.inject_dependencies("logger")
    def handle_query(self, data: bytes, valid_client_ipv4: ipaddress.IPv4Address, is_plaintext: bool, logger: Logger) -> Optional[bytes]:
        address_to_translate = (self._parse_plaintext_address_to_translate(data) if is_plaintext else self._parse_binary_address_to_translate(data))
        if address_to_translate is None:
            logger.debug(f"An invalid SAQ message has been received from {valid_client_ipv4}!", LogFacilities.SAQ_CLIENT_INVALID_MESSAGE)
            return None

        try:
            translated_address = self._perform_address_translation(address_to_translate, valid_client_ipv4)
        except (SubstituteAssignmentNotFoundExc, SubstituteIPv4AddressNotAllowedExc, IPv6AddressNotSubstitutableExc, SubstituteAddressSpaceCurrentlyFullExc) as e:
            logger.debug(f"Query ERROR: '{address_to_translate}' -> {e.__class__.__name__} {{client: {valid_client_ipv4}}}", LogFacilities.SAQ_QUERY_ERROR)
            return None

        logger.debug(f"Query SUCCESS: '{address_to_translate}' -> '{translated_address}' {{client: {valid_client_ipv4}}}", LogFacilities.SAQ_QUERY_SUCCESS)
        return str(translated_address).encode("ascii") if is_plaintext else translated_address.packed

    def _parse_binary_address_to_translate(self, data: bytes) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
        data_len = len(data)

        if data_len == 4:
            return ipaddress.IPv4Address(data)

        if data_len == 16:
            return ipaddress.IPv6Address(data)

        return None

    def _parse_plaintext_address_to_translate(self, data: bytes) -> Optional[Union[ipaddress.IPv4Address, ipaddress.IPv6Address]]:
        try:
            data_string = data.decode("ascii")
        except UnicodeError:
            return None

        data_string = data_string.strip()

        try:
            return ipaddress.ip_address(data_string)
        except ValueError:
            return None

    @DI_NS.inject_dependencies("substitute_address_mapper")
    def _perform_address_translation(self, address_to_translate: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], valid_client_ipv4: ipaddress.IPv4Address, substitute_address_mapper: SubstituteAddressMapper) -> Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
        if isinstance(address_to_translate, ipaddress.IPv4Address):
            return substitute_address_mapper.map_substitute_4to6(address_to_translate, valid_client_ipv4)[0]

        if isinstance(address_to_translate, ipaddress.IPv6Address):
            return substitute_address_mapper.map_substitute_6to4(address_to_translate, valid_client_ipv4, mapping_creation_allowed=True)[0]

        raise ThisShouldNeverHappenExc(f"Invalid IP address class: {address_to_translate.__class__.__name__}")
