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


from typing import Union
import ipaddress
from tundra_xaxlib.v1.MessageType import MessageType
from tundra_xaxlib.v1.RequestMessage import RequestMessage
from tundra_xaxlib.v1.SuccessfulResponseMessage import SuccessfulResponseMessage
from tundra_xaxlib.v1.ErroneousResponseMessage import ErroneousResponseMessage
from get4for6.exc.ThisShouldNeverHappenExc import ThisShouldNeverHappenExc
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.addr_mapper.client.ClientAddressMapper import ClientAddressMapper
from get4for6.addr_mapper.client.exc.ClientIPv4AddressNotAllowedExc import ClientIPv4AddressNotAllowedExc
from get4for6.addr_mapper.client.exc.ClientIPv6PrefixIncorrectExc import ClientIPv6PrefixIncorrectExc
from get4for6.addr_mapper.client.exc.ClientIPv6ContainsScopeIDExc import ClientIPv6ContainsScopeIDExc
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.IPv6AddressNotSubstitutableExc import IPv6AddressNotSubstitutableExc
from get4for6.addr_mapper.substitute.exc.SubstituteAddressSpaceCurrentlyFullExc import SubstituteAddressSpaceCurrentlyFullExc
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.SubstituteIPv4AddressNotAllowedExc import SubstituteIPv4AddressNotAllowedExc


class _TundraXAXRequestHandler:
    @DI_NS.inject_dependencies("logger")
    def handle_request(self, request: RequestMessage, logger: Logger) -> Union[SuccessfulResponseMessage, ErroneousResponseMessage]:
        try:
            new_source_ip, new_destination_ip, external_cache_lifetime = self._perform_address_translation(
                message_type=request.message_type,
                old_source_ip=request.source_ip_address,
                old_destination_ip=request.destination_ip_address
            )
        except (ClientIPv4AddressNotAllowedExc, ClientIPv6PrefixIncorrectExc, ClientIPv6ContainsScopeIDExc, SubstituteIPv4AddressNotAllowedExc, IPv6AddressNotSubstitutableExc) as e:
            # For "security errors", translated packets are silently dropped
            response = request.generate_erroneous_response(icmp_bit=False)
            logger.debug(f"Translation security ERROR: {request.message_type.name}; ('{request.source_ip_address}', '{request.destination_ip_address}') -> {e.__class__.__name__}", LogFacilities.XAX_TRANSLATION_ERROR)
        except (SubstituteAssignmentNotFoundExc, SubstituteAddressSpaceCurrentlyFullExc) as f:
            # For "server errors", translated packets are rejected with ICMP error messages, if possible
            response = request.generate_erroneous_response(
                icmp_bit=bool(request.message_type in (MessageType.MT_4TO6_MAIN_PACKET, MessageType.MT_6TO4_MAIN_PACKET))
            )
            logger.debug(f"Translation server ERROR: {request.message_type.name}; ('{request.source_ip_address}', '{request.destination_ip_address}') -> {f.__class__.__name__}", LogFacilities.XAX_TRANSLATION_ERROR)
        else:
            response = request.generate_successful_response(
                cache_lifetime=external_cache_lifetime,
                source_ip_address=new_source_ip,
                destination_ip_address=new_destination_ip
            )
            logger.debug(f"Translation SUCCESS: {request.message_type.name}; ('{request.source_ip_address}', '{request.destination_ip_address}') -> ('{response.source_ip_address}', '{response.destination_ip_address}')", LogFacilities.XAX_TRANSLATION_SUCCESS)

        return response

    def _perform_address_translation(self, message_type: MessageType, old_source_ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address], old_destination_ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> tuple[Union[ipaddress.IPv4Address, ipaddress.IPv6Address], Union[ipaddress.IPv4Address, ipaddress.IPv6Address], int]:
        try:
            xlat_function = ({
                MessageType.MT_4TO6_MAIN_PACKET: self._perform_4to6_main_packet_address_translation,
                MessageType.MT_4TO6_ICMP_ERROR_PACKET: self._perform_4to6_icmp_error_packet_address_translation,
                MessageType.MT_6TO4_MAIN_PACKET: self._perform_6to4_main_packet_address_translation,
                MessageType.MT_6TO4_ICMP_ERROR_PACKET: self._perform_6to4_icmp_error_packet_address_translation
            }[message_type])
        except KeyError:
            raise ThisShouldNeverHappenExc(f"Invalid 'tundra_xaxlib' message type: {message_type}")

        return xlat_function(old_source_ip=old_source_ip, old_destination_ip=old_destination_ip)  # noqa

    @DI_NS.inject_dependencies("client_address_mapper", "substitute_address_mapper")
    def _perform_4to6_main_packet_address_translation(self, old_source_ip: ipaddress.IPv4Address, old_destination_ip: ipaddress.IPv4Address, client_address_mapper: ClientAddressMapper, substitute_address_mapper: SubstituteAddressMapper) -> tuple[ipaddress.IPv6Address, ipaddress.IPv6Address, int]:  # (new source IP, new destination IP, external cache lifetime)
        assert (isinstance(old_source_ip, ipaddress.IPv4Address) and isinstance(old_destination_ip, ipaddress.IPv4Address))  # Make sure the program is not broken

        # This makes sure that the source IP is a valid client IP address
        new_source_ip = client_address_mapper.map_client_4to6(ipv4_address=old_source_ip)

        new_destination_ip, external_cache_lifetime = substitute_address_mapper.map_substitute_4to6(ipv4_address=old_destination_ip, valid_client_ipv4=old_source_ip)

        return new_source_ip, new_destination_ip, external_cache_lifetime

    @DI_NS.inject_dependencies("client_address_mapper", "substitute_address_mapper")
    def _perform_4to6_icmp_error_packet_address_translation(self, old_source_ip: ipaddress.IPv4Address, old_destination_ip: ipaddress.IPv4Address, client_address_mapper: ClientAddressMapper, substitute_address_mapper: SubstituteAddressMapper) -> tuple[ipaddress.IPv6Address, ipaddress.IPv6Address, int]:  # (new source IP, new destination IP, external cache lifetime)
        assert (isinstance(old_source_ip, ipaddress.IPv4Address) and isinstance(old_destination_ip, ipaddress.IPv4Address))  # Make sure the program is not broken

        # This makes sure that the destination IP is a valid client IP address
        new_destination_ip = client_address_mapper.map_client_4to6(ipv4_address=old_destination_ip)

        new_source_ip, external_cache_lifetime = substitute_address_mapper.map_substitute_4to6(ipv4_address=old_source_ip, valid_client_ipv4=old_destination_ip)

        return new_source_ip, new_destination_ip, external_cache_lifetime

    @DI_NS.inject_dependencies("client_address_mapper", "substitute_address_mapper")
    def _perform_6to4_main_packet_address_translation(self, old_source_ip: ipaddress.IPv6Address, old_destination_ip: ipaddress.IPv6Address, client_address_mapper: ClientAddressMapper, substitute_address_mapper: SubstituteAddressMapper) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address, int]:  # (new source IP, new destination IP, external cache lifetime)
        assert (isinstance(old_source_ip, ipaddress.IPv6Address) and isinstance(old_destination_ip, ipaddress.IPv6Address))  # Make sure the program is not broken

        # This makes sure that the destination IP is a valid client IP address
        new_destination_ip = client_address_mapper.map_client_6to4(ipv6_address=old_destination_ip)

        new_source_ip, external_cache_lifetime = substitute_address_mapper.map_substitute_6to4(ipv6_address=old_source_ip, valid_client_ipv4=new_destination_ip, mapping_creation_allowed=True)

        return new_source_ip, new_destination_ip, external_cache_lifetime

    @DI_NS.inject_dependencies("client_address_mapper", "substitute_address_mapper")
    def _perform_6to4_icmp_error_packet_address_translation(self, old_source_ip: ipaddress.IPv6Address, old_destination_ip: ipaddress.IPv6Address, client_address_mapper: ClientAddressMapper, substitute_address_mapper: SubstituteAddressMapper) -> tuple[ipaddress.IPv4Address, ipaddress.IPv4Address, int]:  # (new source IP, new destination IP, external cache lifetime)
        assert (isinstance(old_source_ip, ipaddress.IPv6Address) and isinstance(old_destination_ip, ipaddress.IPv6Address))  # Make sure the program is not broken

        # This makes sure that the source IP is a valid client IP address
        new_source_ip = client_address_mapper.map_client_6to4(ipv6_address=old_source_ip)

        new_destination_ip, external_cache_lifetime = substitute_address_mapper.map_substitute_6to4(ipv6_address=old_destination_ip, valid_client_ipv4=new_source_ip, mapping_creation_allowed=True)

        return new_source_ip, new_destination_ip, external_cache_lifetime
