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
import asyncio
import threading
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.modules.m_dns._dns_qh.DNSQueryHandler import DNSQueryHandler  # noqa


class _DNSTCPClientHandler:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, max_simultaneous_queries_semaphore: threading.BoundedSemaphore):
        self._reader: Final[asyncio.StreamReader] = reader
        self._writer: Final[asyncio.StreamWriter] = writer
        self._max_simultaneous_queries_semaphore: Final[threading.BoundedSemaphore] = max_simultaneous_queries_semaphore

    @DI_NS.inject_dependencies("logger")
    async def handle_client(self, logger: Logger) -> None:
        try:
            await self._handle_client()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"An unexpected exception occurred while handling a TCP DNS client --> {e.__class__.__name__}: {str(e)}", LogFacilities.DNS_CLIENT_UNEXPECTED_EXCEPTION)

    async def _handle_client(self) -> None:
        try:
            await self._handle_client_with_socket_closure_ensured()
        finally:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, EOFError):  # If an error occurs, assume that the connection has already been closed
                pass

    @DI_NS.inject_dependencies("configuration", "logger")
    async def _handle_client_with_socket_closure_ensured(self, configuration: Configuration, logger: Logger) -> None:
        # Get the client's IPv4 and validate it before spending time and resources reading the query from it
        addr_tuple = self._writer.get_extra_info("peername", default=None)
        if addr_tuple is None:
            return

        valid_client_ipv4 = IPHelpers.parse_client_ipv4_from_string_and_validate_it(addr_tuple[0], configuration)
        if valid_client_ipv4 is None:
            logger.debug(f"{repr(addr_tuple[0])} is not a valid client IPv4 address!", LogFacilities.DNS_CLIENT_INVALID_IP)
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

    @DI_NS.inject_dependencies("configuration")
    async def _handle_dns_query(self, valid_client_ipv4: ipaddress.IPv4Address, configuration: Configuration) -> None:
        try:
            query_bytes = await asyncio.wait_for(self._receive_query_via_tcp(), timeout=configuration.dns.tcp_communication_with_client_timeout)
        except asyncio.TimeoutError:
            return

        if query_bytes is None:
            return

        response_bytes = await DNSQueryHandler().handle_query(query_bytes=query_bytes, valid_client_ipv4=valid_client_ipv4, over_tcp=True)
        if response_bytes is None:
            return

        try:
            await asyncio.wait_for(self._send_response_via_tcp(response_bytes), timeout=configuration.dns.tcp_communication_with_client_timeout)
        except asyncio.TimeoutError:
            pass

    async def _receive_query_via_tcp(self) -> Optional[bytes]:
        try:
            length_bytes = await self._reader.readexactly(2)
        except (OSError, EOFError):
            return None

        length = int.from_bytes(length_bytes, byteorder="big", signed=False)
        if length == 0:
            return None

        try:
            return await self._reader.readexactly(length)
        except (OSError, EOFError):
            return None

    async def _send_response_via_tcp(self, response_bytes: bytes) -> None:
        length = len(response_bytes)
        if (length == 0) or (length > 65535):
            return

        length_bytes = length.to_bytes(2, byteorder="big", signed=False)
        response_bytes = (length_bytes + response_bytes)

        try:
            self._writer.write(response_bytes)
            await self._writer.drain()
        except (OSError, EOFError):
            pass
