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
from get4for6.modules.m_dns._DNSDatagramProtocol import _DNSDatagramProtocol
from get4for6.modules.m_dns._DNSUDPClientHandler import _DNSUDPClientHandler


class _DNSUDPClientHandlerDispatcher:
    def __init__(self, transport: asyncio.DatagramTransport, protocol: _DNSDatagramProtocol, max_simultaneous_queries_semaphore: threading.BoundedSemaphore):
        self._transport: Final[asyncio.DatagramTransport] = transport
        self._protocol: Final[_DNSDatagramProtocol] = protocol
        self._max_simultaneous_queries_semaphore: Final[threading.BoundedSemaphore] = max_simultaneous_queries_semaphore
        self._currently_running_client_handlers: Final[set[asyncio.Task]] = set()

    async def run(self) -> None:
        try:
            await self._run()
        except asyncio.CancelledError:
            pass
        finally:
            self._cancel_currently_running_client_handlers()

    def _cancel_currently_running_client_handlers(self) -> None:
        # The set is copied, as it might get changed by done callbacks while cancelling the tasks
        for client_handler in self._currently_running_client_handlers.copy():
            client_handler.cancel()

    async def _run(self) -> None:
        while True:
            data, addr = await self._protocol.wait_for_query_to_be_received()

            # Client handlers are essentially fire-and-forget tasks, which, however, get canceled if this dispatcher
            #  gets canceled
            new_client_handler = asyncio.create_task(_DNSUDPClientHandler(self._transport, data, addr, self._max_simultaneous_queries_semaphore).handle_client())
            self._currently_running_client_handlers.add(new_client_handler)
            new_client_handler.add_done_callback(self._currently_running_client_handlers.remove)
