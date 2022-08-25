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
from tundra_xaxlib.exc.InvalidMessageDataExc import InvalidMessageDataExc
from tundra_xaxlib.v1.V1Constants import V1Constants
from tundra_xaxlib.v1.RequestMessage import RequestMessage
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.modules.m_xax._TundraXAXRequestHandler import _TundraXAXRequestHandler


class _TundraXAXClientHandler:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, is_tcp: bool, max_simultaneous_connections_semaphore: threading.BoundedSemaphore):
        self._reader: Final[asyncio.StreamReader] = reader
        self._writer: Final[asyncio.StreamWriter] = writer
        self._is_tcp: Final[bool] = is_tcp
        self._max_simultaneous_connections_semaphore: Final[threading.BoundedSemaphore] = max_simultaneous_connections_semaphore
        self._request_handler: Final[_TundraXAXRequestHandler] = _TundraXAXRequestHandler()

    @DI_NS.inject_dependencies("logger")
    async def handle_client(self, logger: Logger) -> None:
        try:
            await self._handle_client()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.warning(f"An unexpected exception occurred while handling a Tundra-XAX client --> {e.__class__.__name__}: {str(e)}", LogFacilities.XAX_CLIENT_UNEXPECTED_EXCEPTION)

    async def _handle_client(self) -> None:
        try:
            await self._handle_client_with_communication_errors_handled()
        except (OSError, EOFError):  # If an error occurs, the client will be disconnected
            pass
        finally:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except (OSError, EOFError):  # If an error occurs, assume that the connection has already been closed
                pass

    @DI_NS.inject_dependencies("logger")
    async def _handle_client_with_communication_errors_handled(self, logger: Logger) -> None:
        if not self._max_simultaneous_connections_semaphore.acquire(blocking=False, timeout=None):
            # If it is not possible to serve the client due to the max simultaneous connection limit being reached, disconnect the client
            logger.debug("It is currently not possible to serve new Tundra-XAX clients, as the maximum simultaneous connection limit has been reached!", LogFacilities.XAX_CLIENT_LIMIT_REACHED)
            return

        try:
            await self._handle_client_with_semaphore_acquired()
        finally:
            self._max_simultaneous_connections_semaphore.release()

    @DI_NS.inject_dependencies("logger")
    async def _handle_client_with_semaphore_acquired(self, logger: Logger) -> None:
        peer_description = (f"TCP {repr(self._writer.get_extra_info('peername', default=None))}" if self._is_tcp else "<Unix socket>")

        logger.debug(f"A new Tundra-XAX client has connected from {peer_description}.", LogFacilities.XAX_CLIENT_CONNECT)
        try:
            while True:
                await self._handle_single_client_request()
        except InvalidMessageDataExc as e:  # If an invalid message is received, disconnect the client
            logger.debug(f"An invalid Tundra-XAX message has been received: {str(e)}", LogFacilities.XAX_CLIENT_INVALID_MESSAGE)
        finally:
            logger.debug(f"The Tundra-XAX client on {peer_description} is disconnecting.", LogFacilities.XAX_CLIENT_DISCONNECT)

    async def _handle_single_client_request(self) -> None:
        request = RequestMessage.from_wireformat(await self._reader.readexactly(V1Constants.WIREFORMAT_MESSAGE_SIZE))

        response = self._request_handler.handle_request(request)

        self._writer.write(response.to_wireformat())
        await self._writer.drain()
