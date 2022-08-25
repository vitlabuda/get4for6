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
from get4for6.modules.m_xax._TundraXAXClientHandler import _TundraXAXClientHandler


class TundraExternalAddrXlatModule(ModuleIface):
    _SERVICE: Final[str] = "tundra_external_addr_xlat"
    _BUFFER_SIZE_LIMIT: Final[int] = 512  # 40 bytes should be enough, putting 512 bytes here...

    @DI_NS.inject_dependencies("configuration")
    def __init__(self, configuration: Configuration):
        self._max_simultaneous_connections_semaphore: Final[threading.BoundedSemaphore] = threading.BoundedSemaphore(value=configuration.tundra_external_addr_xlat.max_simultaneous_connections)

    async def run(self) -> None:
        await self._run()

    @DI_NS.inject_dependencies("termination_event", "logger")  # The 'run()' method has no arguments in 'ModuleIface'
    async def _run(self, termination_event: asyncio.Event, logger: Logger) -> None:
        unix_servers, tcp_servers = await self._start_servers()

        logger.info(f"Listening on Unix sockets {repr([unix_path for _, unix_path in unix_servers])} and TCP {repr([ip_port_pair.to_printable_tuple() for _, ip_port_pair in tcp_servers])}.", LogFacilities.XAX)
        await termination_event.wait()

        await self._stop_servers(unix_servers, tcp_servers)

    @DI_NS.inject_dependencies("configuration", "logger")
    async def _start_servers(self, configuration: Configuration, logger: Logger) -> tuple[list[tuple[asyncio.base_events.Server, str]], list[tuple[asyncio.base_events.Server, IPPortPair]]]:
        unix_servers = []
        for unix_path in configuration.tundra_external_addr_xlat.listen_on_unix:
            try:
                new_unix_server = await asyncio.start_unix_server(
                    client_connected_cb=self._client_connected_via_unix,
                    path=unix_path,
                    limit=self.__class__._BUFFER_SIZE_LIMIT,
                    start_serving=True
                )
            except OSError as e:
                raise FailedToStartServerExc.unix(self.__class__._SERVICE, unix_path, str(e))
            else:
                unix_servers.append((new_unix_server, unix_path))
                logger.debug(f"Unix socket server on {repr(unix_path)} has been started.", LogFacilities.XAX_SERVER_START)

        tcp_servers = []
        for ip_port_pair in configuration.tundra_external_addr_xlat.listen_on_tcp:
            try:
                new_tcp_server = await asyncio.start_server(
                    client_connected_cb=self._client_connected_via_tcp,
                    host=str(ip_port_pair.ip_address),
                    port=ip_port_pair.port,
                    limit=self.__class__._BUFFER_SIZE_LIMIT,
                    start_serving=True
                )
            except OSError as f:
                raise FailedToStartServerExc.tcp(self.__class__._SERVICE, ip_port_pair, str(f))
            else:
                tcp_servers.append((new_tcp_server, ip_port_pair))
                logger.debug(f"TCP server on {repr(ip_port_pair.to_printable_tuple())} has been started.", LogFacilities.XAX_SERVER_START)

        return unix_servers, tcp_servers

    @DI_NS.inject_dependencies("logger")
    async def _stop_servers(self, unix_servers: list[tuple[asyncio.base_events.Server, str]], tcp_servers: list[tuple[asyncio.base_events.Server, IPPortPair]], logger: Logger) -> None:
        for unix_server, unix_path in unix_servers:
            try:
                await self._stop_server_with_exceptions_handled(unix_server)
            except OSError as e:
                raise FailedToStopServerExc.unix(self.__class__._SERVICE, unix_path, str(e))
            else:
                logger.debug(f"Unix socket server on {repr(unix_path)} has been stopped.", LogFacilities.XAX_SERVER_STOP)

        for tcp_server, ip_port_pair in tcp_servers:
            try:
                await self._stop_server_with_exceptions_handled(tcp_server)
            except OSError as f:
                raise FailedToStopServerExc.tcp(self.__class__._SERVICE, ip_port_pair, str(f))
            else:
                logger.debug(f"TCP server on {repr(ip_port_pair.to_printable_tuple())} has been stopped.", LogFacilities.XAX_SERVER_STOP)

    async def _stop_server_with_exceptions_handled(self, server: asyncio.base_events.Server) -> None:
        server.close()
        await server.wait_closed()

    async def _client_connected_via_unix(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _TundraXAXClientHandler(
            reader=reader,
            writer=writer,
            is_tcp=False,
            max_simultaneous_connections_semaphore=self._max_simultaneous_connections_semaphore
        ).handle_client()

    async def _client_connected_via_tcp(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _TundraXAXClientHandler(
            reader=reader,
            writer=writer,
            is_tcp=True,
            max_simultaneous_connections_semaphore=self._max_simultaneous_connections_semaphore
        ).handle_client()
