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


from __future__ import annotations
from get4for6.config.IPPortPair import IPPortPair
from get4for6.modules.exc._FailedToStartStopServerBaseExc import _FailedToStartStopServerBaseExc


class FailedToStartServerExc(_FailedToStartStopServerBaseExc):
    def __init__(self, service: str, protocol: str, server_endpoint_repr: str, reason: str):
        _FailedToStartStopServerBaseExc.__init__(self, "start", service, protocol, server_endpoint_repr, reason)

    @classmethod
    def unix(cls, service: str, unix_path: str, reason: str) -> FailedToStartServerExc:
        return cls(service, cls._PROTOCOL_UNIX, repr(unix_path), reason)

    @classmethod
    def tcp(cls, service: str, ip_port_pair: IPPortPair, reason: str) -> FailedToStartServerExc:
        return cls(service, cls._PROTOCOL_TCP, repr(ip_port_pair.to_printable_tuple()), reason)

    @classmethod
    def udp(cls, service: str, ip_port_pair: IPPortPair, reason: str) -> FailedToStartServerExc:
        return cls(service, cls._PROTOCOL_UDP, repr(ip_port_pair.to_printable_tuple()), reason)
