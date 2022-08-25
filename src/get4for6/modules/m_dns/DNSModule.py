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
import asyncio
import threading
from get4for6.config.Configuration import Configuration
from get4for6.config.IPPortPair import IPPortPair
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.modules.ModuleIface import ModuleIface
from get4for6.modules.exc.FailedToStartServerExc import FailedToStartServerExc
from get4for6.modules.exc.FailedToStopServerExc import FailedToStopServerExc
from get4for6.modules.m_dns._DNSDatagramProtocol import _DNSDatagramProtocol
from get4for6.modules.m_dns._DNSTCPClientHandler import _DNSTCPClientHandler
from get4for6.modules.m_dns._DNSUDPClientHandlerDispatcher import _DNSUDPClientHandlerDispatcher


class DNSModule(ModuleIface):
    _SERVICE: Final[str] = "dns"
    _BUFFER_SIZE_LIMIT: Final[int] = 4096

    @DI_NS.inject_dependencies("configuration")
    def __init__(self, configuration: Configuration):
        self._max_simultaneous_queries_semaphore: Final[threading.BoundedSemaphore] = threading.BoundedSemaphore(value=configuration.dns.max_simultaneous_queries)

    async def run(self) -> None:
        await self._run()

    @DI_NS.inject_dependencies("termination_event", "logger")  # The 'run()' method has no arguments in 'ModuleIface'
    async def _run(self, termination_event: asyncio.Event, logger: Logger) -> None:
        tcp_udp_servers = await self._start_servers()

        logger.info(f"Listening on UDP and TCP {repr([tcp_udp_server[4].to_printable_tuple() for tcp_udp_server in tcp_udp_servers])}.", LogFacilities.DNS)
        await termination_event.wait()

        await self._stop_servers(tcp_udp_servers)

    @DI_NS.inject_dependencies("configuration", "logger")
    async def _start_servers(self, configuration: Configuration, logger: Logger) -> list[tuple[asyncio.base_events.Server, asyncio.DatagramTransport, _DNSDatagramProtocol, asyncio.Task, IPPortPair]]:
        loop = asyncio.get_running_loop()
        tcp_udp_servers = []

        for ip_port_pair in configuration.dns.listen_on:
            # UDP
            try:
                transport, protocol = await loop.create_datagram_endpoint(
                    protocol_factory=lambda: _DNSDatagramProtocol(),
                    local_addr=(str(ip_port_pair.ip_address), ip_port_pair.port),
                    remote_addr=None,
                    allow_broadcast=False
                )
            except OSError as f:
                raise FailedToStartServerExc.udp(self.__class__._SERVICE, ip_port_pair, str(f))
            else:
                new_dispatcher_task = asyncio.create_task(_DNSUDPClientHandlerDispatcher(transport, protocol, self._max_simultaneous_queries_semaphore).run())  # noqa

            # TCP
            try:
                new_tcp_server = await asyncio.start_server(
                    client_connected_cb=self._client_connected_via_tcp,
                    host=str(ip_port_pair.ip_address),
                    port=ip_port_pair.port,
                    limit=self.__class__._BUFFER_SIZE_LIMIT,
                    start_serving=True
                )
            except OSError as e:
                raise FailedToStartServerExc.tcp(self.__class__._SERVICE, ip_port_pair, str(e))

            tcp_udp_servers.append((new_tcp_server, transport, protocol, new_dispatcher_task, ip_port_pair))
            logger.debug(f"UDP and TCP server on {repr(ip_port_pair.to_printable_tuple())} has been started.", LogFacilities.DNS_SERVER_START)

        return tcp_udp_servers  # noqa

    @DI_NS.inject_dependencies("logger")
    async def _stop_servers(self, tcp_udp_servers: list[tuple[asyncio.base_events.Server, asyncio.DatagramTransport, _DNSDatagramProtocol, asyncio.Task, IPPortPair]], logger: Logger) -> None:
        for tcp_server, udp_transport, udp_protocol, udp_dispatcher_task, ip_port_pair in tcp_udp_servers:
            # UDP
            udp_dispatcher_task.cancel()
            await udp_dispatcher_task  # This should not raise an exception, not even 'CancelledError'
            try:
                udp_transport.close()
                await udp_protocol.wait_until_closed()
            except OSError as f:
                raise FailedToStopServerExc.udp(self.__class__._SERVICE, ip_port_pair, str(f))

            # TCP
            try:
                tcp_server.close()
                await tcp_server.wait_closed()
            except OSError as e:
                raise FailedToStopServerExc.tcp(self.__class__._SERVICE, ip_port_pair, str(e))

            logger.debug(f"UDP and TCP server on {repr(ip_port_pair.to_printable_tuple())} has been stopped.", LogFacilities.DNS_SERVER_STOP)

    async def _client_connected_via_tcp(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _DNSTCPClientHandler(
            reader=reader,
            writer=writer,
            max_simultaneous_queries_semaphore=self._max_simultaneous_queries_semaphore
        ).handle_client()
