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
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.helpers.IPHelpers import IPHelpers
from get4for6.modules.m_saq._SAQQueryHandler import _SAQQueryHandler


class _SAQClientHandler:
    def __init__(self, transport: asyncio.DatagramTransport, data: bytes, addr: tuple[str, int], is_plaintext: bool):
        self._transport: Final[asyncio.DatagramTransport] = transport
        self._data: Final[bytes] = data
        self._addr: Final[tuple[str, int]] = addr
        self._is_plaintext: Final[bool] = is_plaintext

    @DI_NS.inject_dependencies("logger")
    def handle_client(self, logger: Logger) -> None:
        try:
            self._handle_client()
        except Exception as e:
            logger.warning(f"An unexpected exception occurred while handling a SAQ client --> {e.__class__.__name__}: {str(e)}", LogFacilities.SAQ_CLIENT_UNEXPECTED_EXCEPTION)

    @DI_NS.inject_dependencies("configuration", "logger")
    def _handle_client(self, configuration: Configuration, logger: Logger) -> None:
        valid_client_ipv4 = IPHelpers.parse_client_ipv4_from_string_and_validate_it(self._addr[0], configuration)
        if valid_client_ipv4 is None:
            logger.debug(f"{repr(self._addr[0])} is not a valid client IPv4 address!", LogFacilities.SAQ_CLIENT_INVALID_IP)
            return

        self._handle_client_with_valid_ipv4(valid_client_ipv4)

    def _handle_client_with_valid_ipv4(self, valid_client_ipv4: ipaddress.IPv4Address) -> None:
        # Since queries are handled synchronously (= a query is received, it is handled, and the response is sent back
        #  without any async/await code and in a single thread), there is no need for a mechanism which would limit
        #  the number of simultaneous clients.
        response_data = _SAQQueryHandler().handle_query(self._data, valid_client_ipv4, self._is_plaintext)
        if response_data is None:
            return

        self._transport.sendto(response_data, self._addr)  # Does not raise, 'error_received' is called instead
