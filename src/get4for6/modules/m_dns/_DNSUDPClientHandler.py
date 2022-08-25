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
import asyncio
import threading
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.modules.m_dns._dns_qh.DNSQueryHandler import DNSQueryHandler  # noqa


class _DNSUDPClientHandler:
    def __init__(self, transport: asyncio.DatagramTransport, data: bytes, addr: tuple[str, int], max_simultaneous_queries_semaphore: threading.BoundedSemaphore):
        self._transport: Final[asyncio.DatagramTransport] = transport
        self._data: Final[bytes] = data
        self._addr: Final[tuple[str, int]] = addr
        self._max_simultaneous_queries_semaphore: Final[threading.BoundedSemaphore] = max_simultaneous_queries_semaphore

    @DI_NS.inject_dependencies("logger")
    async def handle_client(self, logger: Logger) -> None:
        try:
            await self._handle_client()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"An unexpected exception occurred while handling a UDP DNS client --> {e.__class__.__name__}: {str(e)}", LogFacilities.DNS_CLIENT_UNEXPECTED_EXCEPTION)

    @DI_NS.inject_dependencies("configuration", "logger")
    async def _handle_client(self, configuration: Configuration, logger: Logger) -> None:
        # Validate the client's IPv4 address before spending time and resources carrying out the query
        valid_client_ipv4 = IPHelpers.parse_client_ipv4_from_string_and_validate_it(self._addr[0], configuration)
        if valid_client_ipv4 is None:
            logger.debug(f"{repr(self._addr[0])} is not a valid client IPv4 address!", LogFacilities.DNS_CLIENT_INVALID_IP)
            return

        # If the client's IPv4 is valid, proceed further
        await self._handle_client_with_valid_ipv4(valid_client_ipv4)

    @DI_NS.inject_dependencies("logger")
    async def _handle_client_with_valid_ipv4(self, valid_client_ipv4: ipaddress.IPv4Address, logger: Logger) -> None:
        if not self._max_simultaneous_queries_semaphore.acquire(blocking=False, timeout=None):
            # If it is not possible to serve the client due to the max simultaneous query limit being reached, disconnect the client
            logger.debug("It is currently not possible to answer DNS queries, as the maximum simultaneous query limit has been reached!", LogFacilities.DNS_CLIENT_LIMIT_REACHED)
            return

        try:
            await self._handle_dns_query(valid_client_ipv4)
        finally:
            self._max_simultaneous_queries_semaphore.release()

    async def _handle_dns_query(self, valid_client_ipv4: ipaddress.IPv4Address) -> None:
        response_bytes = await DNSQueryHandler().handle_query(query_bytes=self._data, valid_client_ipv4=valid_client_ipv4, over_tcp=False)
        if response_bytes is None:
            return

        self._transport.sendto(response_bytes, self._addr)  # Does not raise, 'error_received' on the protocol object is called instead
