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


import asyncio
from get4for6.config.Configuration import Configuration
from get4for6.di import DI_NS
from get4for6.logger.Logger import Logger
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.modules.ModuleIface import ModuleIface
from get4for6.modules.m_xax.TundraExternalAddrXlatModule import TundraExternalAddrXlatModule
from get4for6.modules.m_dns.DNSModule import DNSModule
from get4for6.modules.m_saq.SimpleAddrQueryModule import SimpleAddrQueryModule
from get4for6.modules.m_printmap.PrintMapModule import PrintMapModule
from get4for6.modules.manager.exc.ModuleTerminatedPrematurelyExc import ModuleTerminatedPrematurelyExc


class ModuleManager:
    async def run(self) -> None:
        modules_to_run = self._decide_which_modules_to_run()

        running_modules = self._start_modules(modules_to_run)
        await self._monitor_modules(running_modules)

    @DI_NS.inject_dependencies("configuration")
    def _decide_which_modules_to_run(self, configuration: Configuration) -> list[ModuleIface]:
        modules_to_run = [
            PrintMapModule(),
            TundraExternalAddrXlatModule()
        ]

        if configuration.dns is not None:
            modules_to_run.append(DNSModule())

        if configuration.simple_addr_query is not None:
            modules_to_run.append(SimpleAddrQueryModule())

        return modules_to_run

    @DI_NS.inject_dependencies("logger")
    def _start_modules(self, modules_to_run: list[ModuleIface], logger: Logger) -> set[asyncio.Task]:
        started_modules = set()
        for module_to_run in modules_to_run:
            module_name = module_to_run.__class__.__name__

            started_module = asyncio.create_task(module_to_run.run(), name=module_name)
            started_modules.add(started_module)

            logger.debug(f"The module {repr(module_name)} has been started.", LogFacilities.MODULE_START)

        return started_modules

    async def _monitor_modules(self, running_modules: set[asyncio.Task]) -> None:
        while running_modules:
            stopped_modules, running_modules = await asyncio.wait(running_modules, timeout=None, return_when=asyncio.FIRST_COMPLETED)

            for stopped_module in stopped_modules:
                await self._handle_stopped_module(stopped_module)

    @DI_NS.inject_dependencies("termination_event", "logger")
    async def _handle_stopped_module(self, stopped_module: asyncio.Task, termination_event: asyncio.Event, logger: Logger) -> None:
        # If an exception has been raised, this will "forward" it
        await stopped_module

        module_name = stopped_module.get_name()
        if not termination_event.is_set():
            raise ModuleTerminatedPrematurelyExc(module_name)

        logger.debug(f"The module {repr(module_name)} has been stopped.", LogFacilities.MODULE_STOP)
