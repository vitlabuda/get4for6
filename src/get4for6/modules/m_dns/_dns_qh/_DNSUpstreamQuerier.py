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


import dns.message
import dns.flags
import dns.exception
import dns.asyncquery
import dns.rcode
import dns.flags
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.modules.m_dns._dns_qh._DNSResolutionFailureInternalExc import _DNSResolutionFailureInternalExc


class _DNSUpstreamQuerier:
    async def perform_upstream_query(self, query_msg: dns.message.Message, over_tcp: bool) -> dns.message.Message:
        """
        CONTEXT: 'query_msg' is a valid DNS query message.

        If an NXDOMAIN or empty NOERROR response is received, it is returned.

        :raises _DNSResolutionFailureInternalExc
        """

        assert (dns.flags.QR not in query_msg.flags)

        try:
            return await self._perform_upstream_query(query_msg, over_tcp)
        except dns.exception.DNSException:
            raise _DNSResolutionFailureInternalExc()

    @DI_NS.inject_dependencies("configuration")
    async def _perform_upstream_query(self, query_msg: dns.message.Message, over_tcp: bool, configuration: Configuration) -> dns.message.Message:
        # Queries sent to upstream servers must desire recursion.
        if dns.flags.RD not in query_msg.flags:
            raise _DNSResolutionFailureInternalExc()

        # The upstream server sequence might be empty, in which case the entire for loop is skipped and a SERVFAIL
        #  response is sent back to the client on whose behalf the query is performed.
        for ip_port_pair in configuration.dns.upstream_servers:
            try:
                if over_tcp:
                    response_msg = await dns.asyncquery.tcp(
                        q=query_msg,
                        where=str(ip_port_pair.ip_address),
                        port=ip_port_pair.port,
                        timeout=configuration.dns.upstream_query_timeout
                    )
                else:
                    response_msg, _ = await dns.asyncquery.udp_with_fallback(
                        q=query_msg,
                        where=str(ip_port_pair.ip_address),
                        port=ip_port_pair.port,
                        timeout=configuration.dns.upstream_query_timeout
                    )
            except dns.exception.DNSException:
                continue

            # Some of these *basic* (i.e. the response is not guaranteed to be *completely* valid, but the basics should
            #  be OK) checks are not necessary, as the 'dnspython' library checks whether the response responds to the
            #  question asked (and raises 'dns.query.BadResponse' if not), but we perform them anyway to make sure that
            #  the code which later works with the response will not receive completely wrong data
            if (
                (response_msg.rcode() not in (dns.rcode.NOERROR, dns.rcode.NXDOMAIN)) or
                (response_msg.id != query_msg.id) or
                (response_msg.opcode() != query_msg.opcode()) or
                (dns.flags.QR not in response_msg.flags) or
                (dns.flags.TC in response_msg.flags) or
                ((dns.flags.RD in response_msg.flags) != (dns.flags.RD in query_msg.flags)) or
                (dns.flags.RA not in response_msg.flags) or  # The upstream server must support recursion
                (response_msg.xfr != query_msg.xfr) or
                (len(response_msg.question) != len(query_msg.question))
            ):
                continue

            # From the client's perspective, the response is no longer authoritative, since it is forwarded to it.
            response_msg.flags &= (~dns.flags.AA)

            return response_msg

        raise _DNSResolutionFailureInternalExc()
