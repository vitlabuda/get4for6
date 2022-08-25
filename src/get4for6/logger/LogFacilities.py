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


from typing import final, Final
from get4for6.etc.UninstantiableClassMixin import UninstantiableClassMixin


@final
class LogFacilities(UninstantiableClassMixin):
    DEFAULT: Final[str] = "-"

    LOGGER_START: Final[str] = "logger.start"
    LOGGER_STOP: Final[str] = "logger.stop"

    MODULE_START: Final[str] = "module.start"
    MODULE_STOP: Final[str] = "module.stop"

    XAX: Final[str] = "tundra_external_addr_xlat"
    XAX_SERVER_START: Final[str] = "tundra_external_addr_xlat.server_start"
    XAX_SERVER_STOP: Final[str] = "tundra_external_addr_xlat.server_stop"
    XAX_CLIENT_UNEXPECTED_EXCEPTION: Final[str] = "tundra_external_addr_xlat.client_unexpected_exception"
    XAX_CLIENT_CONNECT: Final[str] = "tundra_external_addr_xlat.client_connect"
    XAX_CLIENT_DISCONNECT: Final[str] = "tundra_external_addr_xlat.client_disconnect"
    XAX_CLIENT_INVALID_MESSAGE: Final[str] = "tundra_external_addr_xlat.invalid_message"
    XAX_CLIENT_LIMIT_REACHED: Final[str] = "tundra_external_addr_xlat.client_limit_reached"
    XAX_TRANSLATION_SUCCESS: Final[str] = "tundra_external_addr_xlat.translation_success"
    XAX_TRANSLATION_ERROR: Final[str] = "tundra_external_addr_xlat.translation_error"

    DNS: Final[str] = "dns"
    DNS_SERVER_START: Final[str] = "dns.server_start"
    DNS_SERVER_STOP: Final[str] = "dns.server_stop"
    DNS_CLIENT_UNEXPECTED_EXCEPTION: Final[str] = "dns.client_unexpected_exception"
    DNS_CLIENT_UNEXPECTED_DNS_EXCEPTION: Final[str] = "dns.client_unexpected_dns_exception"
    DNS_CLIENT_INVALID_IP: Final[str] = "dns.client_invalid_ip"
    DNS_CLIENT_INVALID_MESSAGE: Final[str] = "dns.client_invalid_message"
    DNS_CLIENT_LIMIT_REACHED: Final[str] = "dns.client_limit_reached"
    DNS_QUERY_SUCCESS: Final[str] = "dns.query_success"
    DNS_QUERY_ERROR: Final[str] = "dns.query_error"

    SAQ: Final[str] = "simple_addr_query"
    SAQ_SERVER_START: Final[str] = "simple_addr_query.server_start"
    SAQ_SERVER_STOP: Final[str] = "simple_addr_query.server_stop"
    SAQ_CLIENT_UNEXPECTED_EXCEPTION: Final[str] = "simple_addr_query.client_unexpected_exception"
    SAQ_CLIENT_INVALID_IP: Final[str] = "simple_addr_query.client_invalid_ip"
    SAQ_CLIENT_INVALID_MESSAGE: Final[str] = "simple_addr_query.client_invalid_message"
    SAQ_QUERY_SUCCESS: Final[str] = "simple_addr_query.query_success"
    SAQ_QUERY_ERROR: Final[str] = "simple_addr_query.query_error"
