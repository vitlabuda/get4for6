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
from get4for6.config.Configuration import Configuration
from get4for6.config.IPPortPair import IPPortPair
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.modules.ModuleIface import ModuleIface
from get4for6.modules.exc.FailedToStartServerExc import FailedToStartServerExc
from get4for6.modules.exc.FailedToStopServerExc import FailedToStopServerExc
from get4for6.modules.m_saq._SAQDatagramProtocol import _SAQDatagramProtocol


class SimpleAddrQueryModule(ModuleIface):
    _SERVICE: Final[str] = "simple_addr_query"

    async def run(self) -> None:
        await self._run()

    @DI_NS.inject_dependencies("termination_event", "logger")  # The 'run()' method has no arguments in 'ModuleIface'
    async def _run(self, termination_event: asyncio.Event, logger: Logger) -> None:
        servers = await self._start_servers()

        logger.info(f"Listening on UDP {repr([server[2].to_printable_tuple() for server in servers if not server[3]])} for binary requests and on UDP {repr([server[2].to_printable_tuple() for server in servers if server[3]])} for plaintext requests.", LogFacilities.SAQ)
        await termination_event.wait()

        await self._stop_servers(servers)

    @DI_NS.inject_dependencies("configuration")
    async def _start_servers(self, configuration: Configuration) -> list[tuple[asyncio.DatagramTransport, _SAQDatagramProtocol, IPPortPair, bool]]:
        binary_servers = []
        for ip_port_pair in configuration.simple_addr_query.listen_on_binary:
            transport, protocol = await self._start_server(ip_port_pair=ip_port_pair, is_plaintext=False)
            binary_servers.append((transport, protocol, ip_port_pair, False))

        plaintext_servers = []
        for ip_port_pair in configuration.simple_addr_query.listen_on_plaintext:
            transport, protocol = await self._start_server(ip_port_pair=ip_port_pair, is_plaintext=True)
            plaintext_servers.append((transport, protocol, ip_port_pair, True))

        return binary_servers + plaintext_servers

    @DI_NS.inject_dependencies("logger")
    async def _start_server(self, ip_port_pair: IPPortPair, is_plaintext: bool, logger: Logger) -> tuple[asyncio.DatagramTransport, _SAQDatagramProtocol]:
        loop = asyncio.get_running_loop()
        local_addr = (str(ip_port_pair.ip_address), ip_port_pair.port)

        try:
            transport, protocol = await loop.create_datagram_endpoint(
                protocol_factory=lambda: _SAQDatagramProtocol(is_plaintext),
                local_addr=local_addr,
                remote_addr=None,
                allow_broadcast=False
            )
        except OSError as e:
            raise FailedToStartServerExc.udp(self.__class__._SERVICE, ip_port_pair, str(e))
        else:
            logger.debug(f"UDP {'plaintext' if is_plaintext else 'binary'} server on {repr(ip_port_pair.to_printable_tuple())} has been started.", LogFacilities.SAQ_SERVER_START)

        return transport, protocol  # noqa

    @DI_NS.inject_dependencies("logger")
    async def _stop_servers(self, servers: list[tuple[asyncio.DatagramTransport, _SAQDatagramProtocol, IPPortPair, bool]], logger: Logger) -> None:
        for transport, protocol, ip_port_pair, is_plaintext in servers:
            try:
                transport.close()
                await protocol.wait_until_closed()
            except OSError as e:
                raise FailedToStopServerExc.udp(self.__class__._SERVICE, ip_port_pair, str(e))
            else:
                logger.debug(f"UDP {'plaintext' if is_plaintext else 'binary'} server on {repr(ip_port_pair.to_printable_tuple())} has been stopped.", LogFacilities.SAQ_SERVER_STOP)
