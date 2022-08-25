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


from typing import Final, Optional
import ipaddress
import dns.message
import dns.name
import dns.flags
import dns.rdata
import dns.rrset
import dns.rcode
import dns.rdataclass
import dns.rdatatype
import dns.rdtypes.ANY.SOA
import dns.rdtypes.ANY.NS
import dns.rdtypes.IN.A
import dns.rdtypes.IN.AAAA
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.addr_mapper.substitute.exc.SubstituteIPv4AddressNotAllowedExc import SubstituteIPv4AddressNotAllowedExc
from get4for6.addr_mapper.substitute.exc.SubstituteAssignmentNotFoundExc import SubstituteAssignmentNotFoundExc
from get4for6.addr_mapper.substitute.exc.IPv6AddressNotSubstitutableExc import IPv6AddressNotSubstitutableExc
from get4for6.addr_mapper.substitute.exc.SubstituteAddressSpaceCurrentlyFullExc import SubstituteAddressSpaceCurrentlyFullExc
from get4for6.modules.m_dns._dns_qh._DNSResolutionFailureInternalExc import _DNSResolutionFailureInternalExc


class _DNSAuxiliaryNameQueryResolver:
    _4TO6_SUBDOMAIN: Final[str] = "r"
    _NS_SUBDOMAIN: Final[str] = "ns"
    _SOA_EMAIL_PART_BEFORE_DOMAIN: Final[str] = "nobody"
    _SOA_SERIAL: Final[int] = 1

    @DI_NS.inject_dependencies("configuration")
    def generate_ipv6_ptr_name(self, ipv6_address: ipaddress.IPv6Address, configuration: Configuration) -> dns.name.Name:
        """
        CONTEXT: This method is called only if auxiliary names are enabled.
        """

        return dns.name.from_text(f"{ipv6_address.exploded.replace(':', '-')}.{configuration.dns.auxiliary_names.domain}")

    @DI_NS.inject_dependencies("configuration")
    def resolve_auxiliary_name_query(self, query_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, configuration: Configuration) -> dns.message.Message:
        """
        CONTEXT: 'query_msg' is a valid DNS query message whose 'question' section contains exactly one question with
         rdclass IN, rdtype other than PTR, and qname being equal to the configured-provided auxiliary domain or a
         subdomain thereof, and whose 'answer', 'authority' and 'additional' sections are empty. This method is called
         only if auxiliary names are enabled.
        """

        auxiliary_domain = dns.name.from_text(configuration.dns.auxiliary_names.domain)
        question = query_msg.question[0]

        auxiliary_subdomain, extracted_auxiliary_domain = self._safe_name_split(question.name, len(auxiliary_domain.labels))
        if auxiliary_domain != extracted_auxiliary_domain:
            raise _DNSResolutionFailureInternalExc()  # This should never happen

        auxiliary_subdomain_nlabels = len(auxiliary_subdomain.labels)
        if auxiliary_subdomain_nlabels == 0:
            # If the queried name has no subdomain, i.e. it is equal to the configured auxiliary domain, respond to SOA
            #  and NS queries with information about the auxiliary name DNS zone, for which is this DNS resolver
            #  authoritative.
            if question.rdtype == dns.rdatatype.SOA:
                response_rrset = self._resolve_soa_query(question.name)
            elif question.rdtype == dns.rdatatype.NS:
                response_rrset = self._resolve_ns_query(question.name)
            else:
                response_rrset = None
        elif auxiliary_subdomain_nlabels == 1:
            # A single DNS label in front of the configured auxiliary domain can be either equal to "ns", which means
            #  that the client is querying for information about this authoritative DNS resolver, or it can be an
            #  IPv6 address (whose colons have been replaced with hyphens), which means that the client wants to be
            #  provided with a substitute IPv4 for that address. Since the string "ns" cannot be converted to an IPv6
            #  address, there is no ambiguity.
            if auxiliary_subdomain.to_text(omit_final_dot=True).lower() == self.__class__._NS_SUBDOMAIN.lower():
                response_rrset = self._resolve_query_for_ns_ips(question.name, question.rdtype)
            else:
                response_rrset = self._resolve_6to4_auxiliary_name_query(auxiliary_subdomain, question.name, question.rdtype, valid_client_ipv4)
        elif auxiliary_subdomain_nlabels == 2:
            # If there are two DNS labels in front of the configured auxiliary domain, check whether the second one
            #  is equal to "r" (= reverse, from the address translator's point of view), which means that the first
            #  label should be considered a substitute IPv4 address (whose dots have been replaced with hyphens), for
            #  which the client wants to get the substituted IPv6 address.
            ipv4_subdomain, _4to6_subdomain = self._safe_name_split(auxiliary_subdomain, 1)
            if _4to6_subdomain.to_text(omit_final_dot=True).lower() != self.__class__._4TO6_SUBDOMAIN.lower():
                return self._generate_empty_response_with_soa_record(query_msg, dns.rcode.NXDOMAIN)

            response_rrset = self._resolve_4to6_auxiliary_name_query(ipv4_subdomain, question.name, question.rdtype, valid_client_ipv4)
        else:
            return self._generate_empty_response_with_soa_record(query_msg, dns.rcode.NXDOMAIN)

        # If the routine resolving the query did not raise an exception, but it returned None instead of a RRset, an
        #  empty NOERROR response will be sent back to the client.
        if response_rrset is None:
            return self._generate_empty_response_with_soa_record(query_msg, dns.rcode.NOERROR)

        response_msg = dns.message.make_response(query_msg, recursion_available=True)
        response_msg.set_rcode(dns.rcode.NOERROR)
        response_msg.flags |= dns.flags.AA  # This DNS resolver is authoritative for the configured auxiliary domain
        response_msg.answer.append(response_rrset)

        return response_msg

    def _safe_name_split(self, name_to_split: dns.name.Name, depth: int) -> tuple[dns.name.Name, dns.name.Name]:
        try:
            return name_to_split.split(depth)
        except ValueError:
            raise _DNSResolutionFailureInternalExc()

    @DI_NS.inject_dependencies("substitute_address_mapper")
    def _resolve_4to6_auxiliary_name_query(self, ipv4_subdomain: dns.name.Name, question_name: dns.name.Name, question_rdtype: dns.rdatatype.RdataType, valid_client_ipv4: ipaddress.IPv4Address, substitute_address_mapper: SubstituteAddressMapper) -> Optional[dns.rrset.RRset]:
        try:
            ipv4_address = ipaddress.IPv4Address(ipv4_subdomain.to_text(omit_final_dot=True).replace("-", "."))
        except ValueError:
            raise _DNSResolutionFailureInternalExc()

        try:
            ipv6_address, cache_lifetime = substitute_address_mapper.map_substitute_4to6(ipv4_address, valid_client_ipv4)
        except (SubstituteAssignmentNotFoundExc, SubstituteIPv4AddressNotAllowedExc):
            raise _DNSResolutionFailureInternalExc()

        # If the IPv6 address has been successfully acquired, but the client does not ask for it, return None (= send
        #  back an empty NOERROR response)
        if question_rdtype != dns.rdatatype.AAAA:
            return None

        return dns.rrset.from_rdata(
            question_name,
            cache_lifetime,
            dns.rdtypes.IN.AAAA.AAAA(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.AAAA,
                address=str(ipv6_address)
            )
        )

    @DI_NS.inject_dependencies("substitute_address_mapper")
    def _resolve_6to4_auxiliary_name_query(self, ipv6_subdomain: dns.name.Name, question_name: dns.name.Name, question_rdtype: dns.rdatatype.RdataType, valid_client_ipv4: ipaddress.IPv4Address, substitute_address_mapper: SubstituteAddressMapper) -> Optional[dns.rrset.RRset]:
        try:
            ipv6_address = ipaddress.IPv6Address(ipv6_subdomain.to_text(omit_final_dot=True).replace("-", ":"))
        except ValueError:
            raise _DNSResolutionFailureInternalExc()

        try:
            ipv4_address, cache_lifetime = substitute_address_mapper.map_substitute_6to4(ipv6_address, valid_client_ipv4, mapping_creation_allowed=True)
        except (SubstituteAssignmentNotFoundExc, IPv6AddressNotSubstitutableExc, SubstituteAddressSpaceCurrentlyFullExc):
            raise _DNSResolutionFailureInternalExc()

        # If the IPv4 address has been successfully acquired, but the client does not ask for it, return None (= send
        #  back an empty NOERROR response)
        if question_rdtype != dns.rdatatype.A:
            return None

        return dns.rrset.from_rdata(
            question_name,
            cache_lifetime,
            dns.rdtypes.IN.A.A(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.A,
                address=str(ipv4_address)
            )
        )

    def _resolve_soa_query(self, question_name: dns.name.Name) -> dns.rrset.RRset:
        return self._generate_soa_rrset_for_auxiliary_name_zone(question_name)

    @DI_NS.inject_dependencies("configuration")
    def _resolve_ns_query(self, question_name: dns.name.Name, configuration: Configuration) -> dns.rrset.RRset:
        return dns.rrset.from_rdata(
            question_name,
            0,
            dns.rdtypes.ANY.NS.NS(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.NS,
                target=dns.name.from_text(f"{self.__class__._NS_SUBDOMAIN}.{configuration.dns.auxiliary_names.domain}")
            )
        )

    @DI_NS.inject_dependencies("configuration")
    def _resolve_query_for_ns_ips(self, question_name: dns.name.Name, question_rdtype: dns.rdatatype.RdataType, configuration: Configuration) -> Optional[dns.rrset.RRset]:
        rdata_list = []
        for ip_address in configuration.dns.auxiliary_names.zone_ns_ips:
            if (question_rdtype == dns.rdatatype.A) and (ip_address.version == 4):
                rdata_list.append(dns.rdtypes.IN.A.A(
                    rdclass=dns.rdataclass.IN,
                    rdtype=dns.rdatatype.A,
                    address=str(ip_address)
                ))
            elif (question_rdtype == dns.rdatatype.AAAA) and (ip_address.version == 6):
                rdata_list.append(dns.rdtypes.IN.AAAA.AAAA(
                    rdclass=dns.rdataclass.IN,
                    rdtype=dns.rdatatype.AAAA,
                    address=str(ip_address)
                ))

        if len(rdata_list) == 0:
            return None

        return dns.rrset.from_rdata_list(question_name, 0, rdata_list)

    @DI_NS.inject_dependencies("configuration")
    def _generate_empty_response_with_soa_record(self, query_msg: dns.message.Message, response_rcode: dns.rcode.Rcode, configuration: Configuration) -> dns.message.Message:
        response_rrset = self._generate_soa_rrset_for_auxiliary_name_zone(dns.name.from_text(configuration.dns.auxiliary_names.domain))

        response_msg = dns.message.make_response(query_msg, recursion_available=True)
        response_msg.set_rcode(response_rcode)
        response_msg.flags |= dns.flags.AA
        response_msg.authority.append(response_rrset)

        return response_msg

    @DI_NS.inject_dependencies("configuration")
    def _generate_soa_rrset_for_auxiliary_name_zone(self, name: dns.name.Name, configuration: Configuration) -> dns.rrset.RRset:
        return dns.rrset.from_rdata(
            name,
            0,  # We do not want to deal with negative caching
            dns.rdtypes.ANY.SOA.SOA(
                rdclass=dns.rdataclass.IN,
                rdtype=dns.rdatatype.SOA,
                mname=dns.name.from_text(f"{self.__class__._NS_SUBDOMAIN}.{configuration.dns.auxiliary_names.domain}"),
                rname=dns.name.from_text(f"{self.__class__._SOA_EMAIL_PART_BEFORE_DOMAIN}.{configuration.dns.auxiliary_names.domain}"),
                serial=self.__class__._SOA_SERIAL,
                refresh=5,  # Zone transfers are not supported, so the value does not matter
                retry=3,  # Zone transfers are not supported, so the value does not matter; must be less than REFRESH
                expire=10,  # Zone transfers are not supported, so the value does not matter; must be bigger than REFRESH + RETRY
                minimum=0  # We do not want to deal with negative caching
            )
        )
