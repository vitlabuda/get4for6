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


import ipaddress
import dns.message
import dns.name
import dns.rrset
import dns.rdataclass
import dns.rdatatype
import dns.rcode
import dns.flags
import dns.rdtypes.IN.A
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.IPv6AddressNotSubstitutableExc import IPv6AddressNotSubstitutableExc
from get4for6.addr_mapper.substitute.exc.SubstituteAddressSpaceCurrentlyFullExc import SubstituteAddressSpaceCurrentlyFullExc
from get4for6.modules.m_dns._dns_qh._DNSUpstreamQuerier import _DNSUpstreamQuerier
from get4for6.modules.m_dns._dns_qh._DNSAuxiliaryNameQueryResolver import _DNSAuxiliaryNameQueryResolver
from get4for6.modules.m_dns._dns_qh._DNSResolutionFailureInternalExc import _DNSResolutionFailureInternalExc


class _DNSForwardQueryResolver:
    @DI_NS.inject_dependencies("configuration")
    async def resolve_forward_query(self, query_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool, configuration: Configuration) -> dns.message.Message:
        """
        CONTEXT: 'query_msg' is a valid DNS query message whose 'question' section contains exactly one question with
         rdclass IN and rdtype other than PTR, and whose 'answer', 'authority' and 'additional' sections are empty.
        """

        question = query_msg.question[0]
        if configuration.dns.auxiliary_names is not None:
            auxiliary_domain = dns.name.from_text(configuration.dns.auxiliary_names.domain)
            if (question.name == auxiliary_domain) or question.name.is_subdomain(auxiliary_domain):
                return _DNSAuxiliaryNameQueryResolver().resolve_auxiliary_name_query(query_msg, valid_client_ipv4)

        if question.rdtype == dns.rdatatype.A:
            return await self._resolve_ipv4_query(query_msg, valid_client_ipv4, over_tcp)

        return await _DNSUpstreamQuerier().perform_upstream_query(query_msg, over_tcp)

    async def _resolve_ipv4_query(self, query_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool) -> dns.message.Message:
        upstream_querier = _DNSUpstreamQuerier()

        # Let an upstream server resolve the client's original query for a record of type A.
        response_msg = await upstream_querier.perform_upstream_query(query_msg, over_tcp)  # This response is to the client's original query, so it can be safely sent back any time.
        if response_msg.rcode() != dns.rcode.NOERROR:
            return response_msg  # NXDOMAIN responses are sent back without any further processing.

        for response_rrset in response_msg.answer:
            if (response_rrset.rdclass == dns.rdataclass.IN) and (response_rrset.rdtype == dns.rdatatype.A):
                # If a rrset with rdtype A is found in the ANSWER section, it means that the queried domain name has
                #  an IPv4 address (= the domain is either IPv4-only or dual-stack) which can be sent back to the
                #  client who asked for it.
                return response_msg

        # Otherwise, query an upstream server for the same name, but now for an AAAA record.
        ipv6_query_msg = dns.message.make_query(
            qname=query_msg.question[0].name,
            rdclass=dns.rdataclass.IN,
            rdtype=dns.rdatatype.AAAA,
            flags=(dns.flags.RD if (dns.flags.RD in query_msg.flags) else 0)
        )
        ipv6_response_msg = await upstream_querier.perform_upstream_query(ipv6_query_msg, over_tcp)
        if ipv6_response_msg.rcode() != dns.rcode.NOERROR:
            # If everything is working correctly, this should not happen (the domain name has been confirmed to exist
            #  by the original query), so it is considered a *temporary* server error.
            raise _DNSResolutionFailureInternalExc()

        for ipv6_rrset in ipv6_response_msg.answer:
            # Since it is possible that a CNAME record has been received, a rrset in the ANSWER section with the wanted
            #  class and type will be considered the target one (this is obviously not the most intelligent behaviour,
            #  but it should get the job done).
            if (ipv6_rrset.rdclass == dns.rdataclass.IN) and (ipv6_rrset.rdtype == dns.rdatatype.AAAA):
                break  # 'ipv6_rrset' will contain the correct RRset
        else:
            # If the queried domain name exists, but has neither IPv4 nor IPv6 addresses, return the original empty
            #  NOERROR response.
            return response_msg

        # At this point, it has been confirmed that the domain is IPv6-only, so we acquire substitute IPv4 addresses
        #  for the above obtained IPv6 addresses, and add them into the response message.
        ipv4_rrset = self._generate_ipv4_rrset_by_substituting_ipv6_rrset(ipv6_rrset, valid_client_ipv4)
        response_msg.answer.append(ipv4_rrset)

        # NOERROR messages without an appropriate answer contain a SOA record in their AUTHORITY section, which must
        #  be removed, since the message is being transformed into a NOERROR message *with* an appropriate answer
        #  (IPv4 RRset).
        response_msg.authority = [item for item in response_msg.authority if ((item.rdclass != dns.rdataclass.IN) or (item.rdtype != dns.rdatatype.SOA))]

        return response_msg

    @DI_NS.inject_dependencies("configuration", "substitute_address_mapper")
    def _generate_ipv4_rrset_by_substituting_ipv6_rrset(self, ipv6_rrset: dns.rrset.RRset, valid_client_ipv4: ipaddress.IPv4Address, configuration: Configuration, substitute_address_mapper: SubstituteAddressMapper) -> dns.rrset.RRset:
        # Parse the IPv6 addresses from the RRSet
        ipv6_addresses = []
        for ipv6_rdata in ipv6_rrset:
            try:
                ipv6_address = ipaddress.IPv6Address(ipv6_rdata.address)
            except ValueError:
                pass  # This should theoretically never happen
            else:
                ipv6_addresses.append(ipv6_address)

        ipv4_addresses = []
        cache_lifetimes = [ipv6_rrset.ttl]

        # Prioritize IPv6 addresses which already have substitute IPv4 assignments, so that the limited address space is not wasted
        unsubstituted_ipv6_addresses = []
        for ipv6_address in ipv6_addresses:
            try:
                ipv4_address, cache_lifetime = substitute_address_mapper.map_substitute_6to4(ipv6_address, valid_client_ipv4, mapping_creation_allowed=False)
            except (SubstituteAssignmentNotFoundExc, IPv6AddressNotSubstitutableExc, SubstituteAddressSpaceCurrentlyFullExc):
                unsubstituted_ipv6_addresses.append(ipv6_address)
            else:
                ipv4_addresses.append(ipv4_address)
                cache_lifetimes.append(cache_lifetime)

        # Then, if there is "not enough" substituted addresses yet, attempt to create new mappings
        remaining_to_substitute = (configuration.dns.max_newly_assigned_substitute_addrs_per_response - len(ipv4_addresses))
        if remaining_to_substitute > 0:
            for _, ipv6_address in zip(range(remaining_to_substitute), unsubstituted_ipv6_addresses):  # This zip() is there to limit the number of iterations
                try:
                    ipv4_address, cache_lifetime = substitute_address_mapper.map_substitute_6to4(ipv6_address, valid_client_ipv4, mapping_creation_allowed=True)
                except (SubstituteAssignmentNotFoundExc, IPv6AddressNotSubstitutableExc, SubstituteAddressSpaceCurrentlyFullExc):
                    pass
                else:
                    ipv4_addresses.append(ipv4_address)
                    cache_lifetimes.append(cache_lifetime)

        if len(ipv4_addresses) == 0:
            # The fact that it was not possible to get any substitute IPv4 addresses at this point might be caused by a
            #  temporary error on this translator's side (e.g. the substitute address space is currently full, but in
            #  a few seconds, it might not be), so we cannot send back an empty NOERROR response to the client, because
            #  it could get negatively cached.
            raise _DNSResolutionFailureInternalExc()

        return dns.rrset.from_rdata_list(
            ipv6_rrset.name,
            min(cache_lifetimes),
            [dns.rdtypes.IN.A.A(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.A,
                address=str(ipv4_address)
            ) for ipv4_address in ipv4_addresses]
        )
