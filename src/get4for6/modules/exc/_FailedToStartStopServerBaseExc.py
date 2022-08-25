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
from typing import Final
import abc
from get4for6.config.IPPortPair import IPPortPair
from get4for6.modules.exc.ModuleBaseExc import ModuleBaseExc


class _FailedToStartStopServerBaseExc(ModuleBaseExc, metaclass=abc.ABCMeta):
    _PROTOCOL_UNIX: Final[str] = "Unix socket"
    _PROTOCOL_TCP: Final[str] = "TCP"
    _PROTOCOL_UDP: Final[str] = "UDP"

    def __init__(self, action: str, service: str, protocol: str, server_endpoint_repr: str, reason: str):
        ModuleBaseExc.__init__(self, f"Failed to {action} {repr(service)} server on {protocol} {server_endpoint_repr}: {reason}")

    @classmethod
    @abc.abstractmethod
    def unix(cls, service: str, unix_path: str, reason: str) -> _FailedToStartStopServerBaseExc:
        raise NotImplementedError(cls.unix.__qualname__)

    @classmethod
    @abc.abstractmethod
    def tcp(cls, service: str, ip_port_pair: IPPortPair, reason: str) -> _FailedToStartStopServerBaseExc:
        raise NotImplementedError(cls.tcp.__qualname__)

    @classmethod
    @abc.abstractmethod
    def udp(cls, service: str, ip_port_pair: IPPortPair, reason: str) -> _FailedToStartStopServerBaseExc:
        raise NotImplementedError(cls.udp.__qualname__)
