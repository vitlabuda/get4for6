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


from typing import Final, NoReturn
import sys
import os
import asyncio
from get4for6.Get4For6Constants import Get4For6Constants
from get4for6.config.Configuration import Configuration
from get4for6.config.TranslationConfiguration import TranslationConfiguration
from get4for6.config.loader.ConfigurationLoader import ConfigurationLoader
from get4for6.config.loader.exc.ConfigLoadingFailureBaseExc import ConfigLoadingFailureBaseExc
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.di import DI_NS
from get4for6.di.Get4For6DependencyProvider import Get4For6DependencyProvider
from get4for6.exc.Get4For6BaseExc import Get4For6BaseExc
from get4for6.addr_mapper.client.ClientAddressMapper import ClientAddressMapper
from get4for6.addr_mapper.substitute.SubstituteAddressMapper import SubstituteAddressMapper
from get4for6.modules.manager.ModuleManager import ModuleManager


class Main:
    _CRASH_MESSAGE_BANNER: Final[str] = "! ERROR:"
    _CRASH_EXIT_CODE: Final[int] = 1

    def main(self) -> None:
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        configuration = self._load_configuration()
        client_address_mapper = self._create_client_address_mapper_instance(configuration.translation)
        substitute_address_mapper = self._create_substitute_address_mapper_instance(configuration.translation)
        termination_event = self.__class__._generate_asyncio_event_for_signals(Get4For6Constants.TERMINATION_SIGNALS)
        print_map_event = self.__class__._generate_asyncio_event_for_signals(Get4For6Constants.PRINT_MAP_SIGNALS)

        with Logger(Get4For6Constants.LOG_OUTPUT_STREAM, configuration.general.print_debug_messages_from) as logger:
            DI_NS.set_dependency_provider(Get4For6DependencyProvider(
                configuration=configuration,
                logger=logger,
                termination_event=termination_event,
                print_map_event=print_map_event,
                client_address_mapper=client_address_mapper,
                substitute_address_mapper=substitute_address_mapper
            ))

            logger.info(f"Get4For6 / v{Get4For6Constants.PROGRAM_VERSION} / Copyright (c) 2022 Vit Labuda", LogFacilities.DEFAULT)
            logger.debug(f"PID: {os.getpid()}", LogFacilities.DEFAULT)

            await self._run_module_manager()

            logger.info("Get4For6 will now terminate.", LogFacilities.DEFAULT)

    def _load_configuration(self) -> Configuration:
        try:
            return ConfigurationLoader().load_config_from_toml_file_specified_in_first_argument()
        except ConfigLoadingFailureBaseExc as e:
            self._crash_on_exception(e)

    def _create_client_address_mapper_instance(self, translation_configuration: TranslationConfiguration) -> ClientAddressMapper:
        return ClientAddressMapper(
            client_allowed_subnets=translation_configuration.client_allowed_subnets,
            map_client_addrs_into=translation_configuration.map_client_addrs_into
        )

    def _create_substitute_address_mapper_instance(self, translation_configuration: TranslationConfiguration) -> SubstituteAddressMapper:
        return SubstituteAddressMapper(
            client_allowed_subnets=translation_configuration.client_allowed_subnets,
            substitute_subnets=translation_configuration.substitute_subnets,
            static_substitute_addr_assignments=translation_configuration.static_substitute_addr_assignments,
            dynamic_substitute_addr_assigning=translation_configuration.dynamic_substitute_addr_assigning
        )

    @staticmethod  # If the method was not static, 'self' would get unnecessarily bound to the inner '_signal_handler' function!
    def _generate_asyncio_event_for_signals(signals: frozenset[int]) -> asyncio.Event:
        loop = asyncio.get_running_loop()
        event = asyncio.Event()

        def _signal_handler() -> None:
            event.set()

        for signal in signals:
            loop.add_signal_handler(signal, _signal_handler)

        return event

    async def _run_module_manager(self) -> None:
        try:
            await ModuleManager().run()
        except Get4For6BaseExc as e:
            self._crash_on_exception(e)

    def _crash_on_exception(self, exception: Get4For6BaseExc) -> NoReturn:
        print(self.__class__._CRASH_MESSAGE_BANNER, str(exception), f"<{exception.__class__.__name__}>", file=sys.stderr, flush=True)
        sys.exit(self.__class__._CRASH_EXIT_CODE)
