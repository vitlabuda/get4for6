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
import dns.message
import dns.name
import dns.reversename
import dns.exception
import dns.rdataclass
import dns.rdatatype
import dns.flags
import dns.rcode
import dns.rrset
import dns.rdtypes.ANY.PTR
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.SubstituteIPv4AddressNotAllowedExc import SubstituteIPv4AddressNotAllowedExc
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.modules.m_dns._dns_qh._DNSUpstreamQuerier import _DNSUpstreamQuerier
from get4for6.modules.m_dns._dns_qh._DNSAuxiliaryNameQueryResolver import _DNSAuxiliaryNameQueryResolver
from get4for6.modules.m_dns._dns_qh._DNSResolutionFailureInternalExc import _DNSResolutionFailureInternalExc


class _DNSReverseQueryResolver:
    @DI_NS.inject_dependencies("configuration")
    async def resolve_reverse_query(self, query_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool, configuration: Configuration) -> dns.message.Message:
        """
        CONTEXT: 'query_msg' is a valid DNS query message whose 'question' section contains exactly one IN PTR
         question, and whose 'answer', 'authority' and 'additional' sections are empty.
        """

        reverse_ip = self._get_ip_address_from_reverse_query(query_msg)
        if isinstance(reverse_ip, ipaddress.IPv4Address) and IPHelpers.is_ipv4_address_part_of_any_subnet_loose(reverse_ip, configuration.translation.substitute_subnets):
            return await self._perform_reverse_query_for_substituted_ipv6_address(query_msg, reverse_ip, valid_client_ipv4, over_tcp)

        return await _DNSUpstreamQuerier().perform_upstream_query(query_msg, over_tcp)

    def _get_ip_address_from_reverse_query(self, query_msg: dns.message.Message) -> Union[ipaddress.IPv4Address, ipaddress.IPv6Address]:
        r_name = query_msg.question[0].name
        try:
            r_addr = dns.reversename.to_address(r_name)
        except dns.exception.SyntaxError:
            raise _DNSResolutionFailureInternalExc()

        try:
            return ipaddress.ip_address(r_addr)
        except ValueError:
            raise _DNSResolutionFailureInternalExc()

    @DI_NS.inject_dependencies("configuration", "substitute_address_mapper")
    async def _perform_reverse_query_for_substituted_ipv6_address(self, query_msg: dns.message.Message, substitute_ipv4: ipaddress.IPv4Address, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool, configuration: Configuration, substitute_address_mapper: SubstituteAddressMapper) -> dns.message.Message:
        # Get the IPv6 address substituted by the provided IPv4 address
        try:
            substituted_ipv6, cache_lifetime = substitute_address_mapper.map_substitute_4to6(substitute_ipv4, valid_client_ipv4)
        except (SubstituteAssignmentNotFoundExc, SubstituteIPv4AddressNotAllowedExc):
            raise _DNSResolutionFailureInternalExc()

        if (configuration.dns.auxiliary_names is not None) and configuration.dns.auxiliary_names.use_for_rdns:
            # If auxiliary names are enabled, and it is desired to use them for reverse DNS, let the auxiliary name
            #  resolver generate an PTR name for the substituted IPv6 address, and mark the DNS answer sent back to the
            #  client as authoritative.
            ptr_names = [_DNSAuxiliaryNameQueryResolver().generate_ipv6_ptr_name(substituted_ipv6)]
            authoritative_answer = True
        else:
            # Otherwise, try answering the query with the substituted IPv6's "real-world" PTR name.
            substituted_ipv6_rdns_name = dns.reversename.from_address(str(substituted_ipv6))
            substitute_query_msg = dns.message.make_query(
                qname=substituted_ipv6_rdns_name,
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.PTR,
                flags=(dns.flags.RD if (dns.flags.RD in query_msg.flags) else 0)
            )
            substitute_response_msg = await _DNSUpstreamQuerier().perform_upstream_query(substitute_query_msg, over_tcp)
            if substitute_response_msg.rcode() != dns.rcode.NOERROR:
                # We cannot send NXDOMAIN responses back, as we do not have a suitable SOA record for the substitute
                #  IPv4 address we are resolving - we send back an SERVFAIL response instead.
                raise _DNSResolutionFailureInternalExc()

            for substitute_response_rrset in substitute_response_msg.answer:
                # Since it is technically (but certainly not likely) possible that a CNAME record has been received
                #  (and we want to ignore it in this case), a RRset in the ANSWER section with the wanted class and type
                #  will be considered the target one (this is obviously not the most intelligent behaviour, but it
                #  should get the job done).
                if (substitute_response_rrset.rdclass == dns.rdataclass.IN) and (substitute_response_rrset.rdtype == dns.rdatatype.PTR):
                    break  # 'substitute_response_rrset' will contain the correct RRset
            else:
                # If the response does not contain a PTR record, send back a SERVFAIL for the same reason as above.
                raise _DNSResolutionFailureInternalExc()

            if len(substitute_response_rrset) == 0:  # Empty RRsets should not exist
                raise _DNSResolutionFailureInternalExc()

            cache_lifetime = min(cache_lifetime, substitute_response_rrset.ttl)
            ptr_names = [rdata.target for rdata in substitute_response_rrset]  # It is technically possible for an IP to have more than one PTR record.
            authoritative_answer = False  # The query is answered by using an upstream server.

        response_rrset = dns.rrset.from_rdata_list(
            query_msg.question[0].name,
            cache_lifetime,
            [dns.rdtypes.ANY.PTR.PTR(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.PTR,
                target=ptr_name
            ) for ptr_name in ptr_names]
        )

        response_msg = dns.message.make_response(query_msg, recursion_available=True)
        response_msg.set_rcode(dns.rcode.NOERROR)
        if authoritative_answer:
            response_msg.flags |= dns.flags.AA
        response_msg.answer.append(response_rrset)

        return response_msg
