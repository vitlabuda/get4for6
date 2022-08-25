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


from typing import Any
import dataclasses
import asyncio
from sidein.providers.DependencyProviderInterface import DependencyProviderInterface
from get4for6.config.Configuration import Configuration
from get4for6.logger.Logger import Logger
from get4for6.di.exc.InvalidGet4For6DependencyRequestedExc import InvalidGet4For6DependencyRequestedExc
from get4for6.addr_mapper.client.ClientAddressMapper import ClientAddressMapper
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper


@dataclasses.dataclass(frozen=True)
class Get4For6DependencyProvider(DependencyProviderInterface):
    configuration: Configuration
    logger: Logger
    termination_event: asyncio.Event
    print_map_event: asyncio.Event
    client_address_mapper: ClientAddressMapper
    substitute_address_mapper: SubstituteAddressMapper

    def get_dependency(self, name: str) -> Any:
        try:
            return vars(self)[name]
        except KeyError:
            raise InvalidGet4For6DependencyRequestedExc(name)
