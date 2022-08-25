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


from typing import Optional
import ipaddress
import dns.message
import dns.rdataclass
import dns.rdatatype
import dns.opcode
import dns.rcode
import dns.exception
import dns.flags
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.modules.m_dns._dns_qh._DNSResolutionFailureInternalExc import _DNSResolutionFailureInternalExc
from get4for6.modules.m_dns._dns_qh._DNSForwardQueryResolver import _DNSForwardQueryResolver
from get4for6.modules.m_dns._dns_qh._DNSReverseQueryResolver import _DNSReverseQueryResolver


class DNSQueryHandler:
    @DI_NS.inject_dependencies("logger")
    async def handle_query(self, query_bytes: bytes, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool, logger: Logger) -> Optional[bytes]:
        try:
            return await self._handle_query(query_bytes, valid_client_ipv4, over_tcp)
        except dns.exception.DNSException as e:
            logger.warning(f"An unexpected DNS exception occurred while handling a DNS query from {valid_client_ipv4} --> {e.__class__.__name__}: {str(e)}", LogFacilities.DNS_CLIENT_UNEXPECTED_DNS_EXCEPTION)
            return None

    @DI_NS.inject_dependencies("logger")
    async def _handle_query(self, query_bytes: bytes, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool, logger: Logger) -> Optional[bytes]:
        query_msg = self._parse_and_validate_query(query_bytes)
        if query_msg is None:
            logger.debug(f"An invalid DNS message has been received from {valid_client_ipv4}!", LogFacilities.DNS_CLIENT_INVALID_MESSAGE)
            return None

        try:
            response_msg = await self._resolve_dns_query(query_msg, valid_client_ipv4, over_tcp)
        except _DNSResolutionFailureInternalExc:
            response_msg = self._make_error_response(query_msg)

        self._make_adjustments_to_response_before_sending_it(response_msg)
        self._log_debug_message_about_query_and_response(query_msg, response_msg, valid_client_ipv4)

        return response_msg.to_wire()

    def _parse_and_validate_query(self, query_bytes: bytes) -> Optional[dns.message.Message]:
        try:
            query_msg = dns.message.from_wire(query_bytes)
        except dns.exception.DNSException:
            return None

        if (
            (dns.flags.QR in query_msg.flags) or
            (dns.flags.AA in query_msg.flags) or
            (dns.flags.TC in query_msg.flags) or
            (dns.flags.RA in query_msg.flags) or
            (query_msg.rcode() != 0) or
            (len(query_msg.question) != 1) or
            (len(query_msg.answer) != 0) or
            (len(query_msg.authority) != 0) or
            (len(query_msg.additional) != 0) or  # dnspython "removes" the EDNS0 'OPT' record from this section, and handles it in a different way
            query_msg.xfr
        ):
            return None

        return query_msg

    async def _resolve_dns_query(self, query_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, over_tcp: bool) -> dns.message.Message:
        if query_msg.opcode() != dns.opcode.QUERY:
            raise _DNSResolutionFailureInternalExc()

        question = query_msg.question[0]
        if question.rdclass != dns.rdataclass.IN:
            raise _DNSResolutionFailureInternalExc()

        # The ANY rdtype is rarely used, and would make some parts of this DNS resolver more complex with little to no
        #  added value. Besides, some DNS implementations/deployments, such as Cloudflare Public DNS (1.1.1.1), do not
        #  support this type of DNS questions as well.
        if question.rdtype == dns.rdatatype.ANY:
            raise _DNSResolutionFailureInternalExc()

        if question.rdtype == dns.rdatatype.PTR:
            return await _DNSReverseQueryResolver().resolve_reverse_query(query_msg, valid_client_ipv4, over_tcp)

        return await _DNSForwardQueryResolver().resolve_forward_query(query_msg, valid_client_ipv4, over_tcp)

    def _make_error_response(self, query_msg: dns.message.Message) -> dns.message.Message:
        response_msg = dns.message.make_response(query_msg, recursion_available=True)
        response_msg.set_rcode(dns.rcode.SERVFAIL)

        return response_msg

    def _make_adjustments_to_response_before_sending_it(self, response_msg: dns.message.Message) -> None:
        # The translator does not perform DNSSEC validation, it communicates with its upstream servers using an
        #  insecure transport, and makes changes to the DNS responses when it performs translation. Therefore, the
        #  response cannot be considered authentic.
        response_msg.flags &= (~dns.flags.AD)

    @DI_NS.inject_dependencies("logger")
    def _log_debug_message_about_query_and_response(self, query_msg: dns.message.Message, response_msg: dns.message.Message, valid_client_ipv4: ipaddress.IPv4Address, logger: Logger) -> None:
        question_repr = repr(query_msg.question)

        response_rcode = response_msg.rcode()
        if response_rcode != dns.rcode.NOERROR:
            try:
                rcode_str = dns.rcode.to_text(response_rcode)
            except ValueError:
                rcode_str = str(response_rcode)

            logger.debug(f"Query ERROR: {question_repr} -> {rcode_str} {{client: {valid_client_ipv4}}}", LogFacilities.DNS_QUERY_ERROR)
            return

        if len(response_msg.answer) == 0:
            logger.debug(f"Query ERROR: {question_repr} -> empty NOERROR {{client: {valid_client_ipv4}}}", LogFacilities.DNS_QUERY_ERROR)
            return

        logger.debug(f"Query SUCCESS: {question_repr} -> {repr(response_msg.answer)} {{client: {valid_client_ipv4}}}", LogFacilities.DNS_QUERY_SUCCESS)
