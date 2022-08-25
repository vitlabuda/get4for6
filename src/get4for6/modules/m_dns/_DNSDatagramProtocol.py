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
import asyncio
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS


class _DNSDatagramProtocol(asyncio.DatagramProtocol):
    @DI_NS.inject_dependencies("configuration")
    def __init__(self, configuration: Configuration):
        self._pending_queries: Final[asyncio.Queue] = asyncio.Queue(maxsize=configuration.dns.max_simultaneous_queries)

        self._close_exc: Optional[Exception] = None
        self._close_exc_available_event: Final[asyncio.Event] = asyncio.Event()

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        pass  # The transport is not needed in this class

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            self._pending_queries.put_nowait((data, addr))
        except asyncio.QueueFull:
            pass  # Can be safely ignored

    async def wait_for_query_to_be_received(self) -> tuple[bytes, tuple[str, int]]:  # (data, addr)
        return await self._pending_queries.get()

    def error_received(self, exc: Exception) -> None:
        pass  # Can be safely ignored

    def connection_lost(self, exc: Optional[Exception]) -> None:
        assert (not self._close_exc_available_event.is_set())

        self._close_exc = exc
        self._close_exc_available_event.set()

    async def wait_until_closed(self) -> None:
        await self._close_exc_available_event.wait()

        if self._close_exc is not None:
            raise self._close_exc
