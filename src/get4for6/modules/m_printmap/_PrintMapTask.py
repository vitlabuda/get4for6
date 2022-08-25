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


from typing import Final, Generator
import ipaddress
import asyncio
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.logger.Logger import Logger


class _PrintMapTask:
    _STATIC_MAPPINGS_BANNER: Final[str] = "--- Static mappings ---"
    _STATIC_MAPPING_PATTERN: Final[str] = "{mapping_ipv4} <-> {mapping_ipv6}"

    _DYNAMIC_MAPPINGS_BANNER_PATTERN: Final[str] = "--- Dynamic mappings for {client_ipv4} ---"
    _DYNAMIC_MAPPING_PATTERN: Final[str] = "{mapping_ipv4} <-> {mapping_ipv6} ... {lifetime_info}"
    _LIFETIME_INFO_REMAINING_PATTERN: Final[str] = "remaining guaranteed lifetime: {remaining_guaranteed_lifetime} seconds"
    _LIFETIME_INFO_MAY_BE_REPLACED: Final[str] = "may be replaced"

    _SECTION_SPACING: Final[int] = 2

    @DI_NS.inject_dependencies("logger")
    def __init__(self, logger: Logger):
        # The logger is called frequently, so it is saved in the instance to save some CPU cycles
        self._logger: Final[Logger] = logger

    async def run(self) -> None:
        try:
            await self._run()
        except asyncio.CancelledError:
            pass

    @DI_NS.inject_dependencies("print_map_event")
    async def _run(self, print_map_event: asyncio.Event) -> None:
        while True:
            await print_map_event.wait()
            print_map_event.clear()

            self._print_mappings()

    @DI_NS.inject_dependencies("substitute_address_mapper")
    def _print_mappings(self, substitute_address_mapper: SubstituteAddressMapper) -> None:
        self._print_static_mappings()

        print_dynamic_mappings_generator = self._print_dynamic_mappings()
        next(print_dynamic_mappings_generator)  # Get to the 'yield'
        substitute_address_mapper.send_dynamic_mappings_to_generator(print_dynamic_mappings_generator)
        del print_dynamic_mappings_generator

        self._write_section_spacing()

    @DI_NS.inject_dependencies("configuration")
    def _print_static_mappings(self, configuration: Configuration) -> None:
        if not configuration.translation.static_substitute_addr_assignments:
            return

        self._write_section_spacing()
        self._write_line(self.__class__._STATIC_MAPPINGS_BANNER)
        for mapping_ipv4, mapping_ipv6 in configuration.translation.static_substitute_addr_assignments:
            self._write_line(self.__class__._STATIC_MAPPING_PATTERN.format(mapping_ipv4=mapping_ipv4, mapping_ipv6=mapping_ipv6))

    def _print_dynamic_mappings(self) -> Generator[None, tuple[ipaddress.IPv4Address, ipaddress.IPv4Address, ipaddress.IPv6Address, int], None]:
        last_client_ipv4 = None

        while True:
            client_ipv4, mapping_ipv4, mapping_ipv6, remaining_guaranteed_lifetime = yield

            if client_ipv4 != last_client_ipv4:
                self._write_section_spacing()
                self._write_line(self.__class__._DYNAMIC_MAPPINGS_BANNER_PATTERN.format(client_ipv4=client_ipv4))
                last_client_ipv4 = client_ipv4

            lifetime_info = (self.__class__._LIFETIME_INFO_REMAINING_PATTERN.format(remaining_guaranteed_lifetime=remaining_guaranteed_lifetime) if (remaining_guaranteed_lifetime > 0) else self.__class__._LIFETIME_INFO_MAY_BE_REPLACED)
            self._write_line(self.__class__._DYNAMIC_MAPPING_PATTERN.format(
                mapping_ipv4=mapping_ipv4,
                mapping_ipv6=mapping_ipv6,
                lifetime_info=lifetime_info
            ))

    def _write_section_spacing(self) -> None:
        for _ in range(self.__class__._SECTION_SPACING):
            self._write_line("")

    def _write_line(self, written_line: str) -> None:
        # For future extension.
        self._logger.write_line_block(written_line)
