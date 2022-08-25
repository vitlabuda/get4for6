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


from typing import Final, Optional
import sys
import fcntl
import tomlkit
import tomlkit.exceptions
from datalidator.exc.DatalidatorExc import DatalidatorExc
from datalidator.blueprints.impl.ObjectBlueprint import ObjectBlueprint
from get4for6.config.Configuration import Configuration
from get4for6.config.GeneralConfiguration import GeneralConfiguration
from get4for6.config.TranslationConfiguration import TranslationConfiguration
from get4for6.config.TundraExternalAddrXlatConfiguration import TundraExternalAddrXlatConfiguration
from get4for6.config.DNSConfiguration import DNSConfiguration
from get4for6.config.SimpleAddrQueryConfiguration import SimpleAddrQueryConfiguration
from get4for6.config.AuxiliaryNamesOptions import AuxiliaryNamesOptions
from get4for6.config.DynamicSubstituteAddrAssigningOptions import DynamicSubstituteAddrAssigningOptions
from get4for6.config.loader._ConfigurationModel import _ConfigurationModel
from get4for6.config.loader._GeneralConfigurationModel import _GeneralConfigurationModel
from get4for6.config.loader._TranslationConfigurationModel import _TranslationConfigurationModel
from get4for6.config.loader._TundraExternalAddrXlatConfigurationModel import _TundraExternalAddrXlatConfigurationModel
from get4for6.config.loader._DNSConfigurationModel import _DNSConfigurationModel
from get4for6.config.loader._SimpleAddrQueryConfigurationModel import _SimpleAddrQueryConfigurationModel
from get4for6.config.loader._AuxiliaryNamesModel import _AuxiliaryNamesModel
from get4for6.config.loader._DynamicSubstituteAddrAssigningModel import _DynamicSubstituteAddrAssigningModel
from get4for6.config.loader._IPPortPairListBlueprint import _IPPortPairListBlueprint
from get4for6.config.loader.exc.ConfigFilePathMissingInFirstArgExc import ConfigFilePathMissingInFirstArgExc
from get4for6.config.loader.exc.FailedToReadConfigFileExc import FailedToReadConfigFileExc
from get4for6.config.loader.exc.FailedToParseConfigExc import FailedToParseConfigExc
from get4for6.config.loader.exc.InvalidConfigContentsExc import InvalidConfigContentsExc
from get4for6.config.loader.exc.NameResolutionFailureExc import NameResolutionFailureExc


class ConfigurationLoader:
    _CONFIGURATION_DICT_BLUEPRINT: Final[ObjectBlueprint] = ObjectBlueprint(
        _ConfigurationModel,
        tag="__config_dict__"
    )

    def load_config_from_toml_file_specified_in_first_argument(self) -> Configuration:
        try:
            toml_file_path = sys.argv[1]
        except IndexError:
            raise ConfigFilePathMissingInFirstArgExc()

        return self.load_config_from_toml_file(toml_file_path.strip())

    def load_config_from_toml_file(self, toml_file_path: str) -> Configuration:
        try:
            with open(toml_file_path, "r") as file_io:
                fcntl.flock(file_io.fileno(), fcntl.LOCK_SH)
                try:
                    toml_string = file_io.read()
                finally:
                    fcntl.flock(file_io.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            raise FailedToReadConfigFileExc(toml_file_path, str(e))

        return self.load_config_from_toml_string(toml_string)

    def load_config_from_toml_string(self, toml_string: str) -> Configuration:
        try:
            parsed_config = tomlkit.loads(toml_string)
        except tomlkit.exceptions.TOMLKitError as e:
            raise FailedToParseConfigExc(str(e))

        return self.load_config_from_dict(dict(parsed_config))

    def load_config_from_dict(self, config_dict: dict) -> Configuration:
        try:
            model = self.__class__._CONFIGURATION_DICT_BLUEPRINT.use(config_dict)
        except _IPPortPairListBlueprint.NameResolutionFailureInBlueprintExc as e:
            raise NameResolutionFailureExc(e.host_name, e.service_name, e.reason, e.get_originator_tag())
        except DatalidatorExc as f:
            raise InvalidConfigContentsExc(str(f), f.get_originator_tag())

        return self._load_config_from_datalidator_model(model)  # noqa

    def _load_config_from_datalidator_model(self, model: _ConfigurationModel) -> Configuration:
        return Configuration(
            general=self._load_general_config_from_datalidator_model(model.general),
            translation=self._load_translation_config_from_datalidator_model(model.translation),
            tundra_external_addr_xlat=self._load_tundra_external_addr_xlat_config_from_datalidator_model(model.tundra_external_addr_xlat),
            dns=self._optionally_load_dns_config_from_datalidator_model(model.dns),
            simple_addr_query=self._optionally_load_simple_addr_query_config_from_datalidator_model(model.simple_addr_query)
        )

    def _load_general_config_from_datalidator_model(self, generic_model: _GeneralConfigurationModel) -> GeneralConfiguration:
        return GeneralConfiguration(
            print_debug_messages_from=frozenset(generic_model.print_debug_messages_from)
        )

    def _load_translation_config_from_datalidator_model(self, translation_model: _TranslationConfigurationModel) -> TranslationConfiguration:
        return TranslationConfiguration(
            client_allowed_subnets=tuple(translation_model.client_allowed_subnets),
            map_client_addrs_into=translation_model.map_client_addrs_into,
            substitute_subnets=tuple(translation_model.substitute_subnets),
            static_substitute_addr_assignments=tuple(translation_model.static_substitute_addr_assignments),
            dynamic_substitute_addr_assigning=self._optionally_load_dynamic_substitute_addr_assigning_options_from_datalidator_model(translation_model.dynamic_substitute_addr_assigning)
        )

    def _load_tundra_external_addr_xlat_config_from_datalidator_model(self, tundra_external_addr_xlat_model: _TundraExternalAddrXlatConfigurationModel) -> TundraExternalAddrXlatConfiguration:
        return TundraExternalAddrXlatConfiguration(
            listen_on_unix=tuple(tundra_external_addr_xlat_model.listen_on_unix),
            listen_on_tcp=tuple(tundra_external_addr_xlat_model.listen_on_tcp),
            max_simultaneous_connections=tundra_external_addr_xlat_model.max_simultaneous_connections
        )

    def _optionally_load_dns_config_from_datalidator_model(self, optional_dns_model: Optional[_DNSConfigurationModel]) -> Optional[DNSConfiguration]:
        if optional_dns_model is None:
            return None

        return DNSConfiguration(
            listen_on=tuple(optional_dns_model.listen_on),
            max_simultaneous_queries=optional_dns_model.max_simultaneous_queries,
            tcp_communication_with_client_timeout=optional_dns_model.tcp_communication_with_client_timeout,
            upstream_servers=tuple(optional_dns_model.upstream_servers),
            upstream_query_timeout=optional_dns_model.upstream_query_timeout,
            max_newly_assigned_substitute_addrs_per_response=optional_dns_model.max_newly_assigned_substitute_addrs_per_response,
            auxiliary_names=self._optionally_load_auxiliary_names_options_from_datalidator_model(optional_dns_model.auxiliary_names)
        )

    def _optionally_load_simple_addr_query_config_from_datalidator_model(self, optional_simple_addr_query_model: Optional[_SimpleAddrQueryConfigurationModel]) -> Optional[SimpleAddrQueryConfiguration]:
        if optional_simple_addr_query_model is None:
            return None

        return SimpleAddrQueryConfiguration(
            listen_on_binary=tuple(optional_simple_addr_query_model.listen_on_binary),
            listen_on_plaintext=tuple(optional_simple_addr_query_model.listen_on_plaintext)
        )

    def _optionally_load_dynamic_substitute_addr_assigning_options_from_datalidator_model(self, optional_dynamic_substitute_addr_assigning_model: Optional[_DynamicSubstituteAddrAssigningModel]) -> Optional[DynamicSubstituteAddrAssigningOptions]:
        if optional_dynamic_substitute_addr_assigning_model is None:
            return None

        return DynamicSubstituteAddrAssigningOptions(
            min_lifetime_after_last_hit=optional_dynamic_substitute_addr_assigning_model.min_lifetime_after_last_hit
        )

    def _optionally_load_auxiliary_names_options_from_datalidator_model(self, optional_auxiliary_names_model: Optional[_AuxiliaryNamesModel]) -> Optional[AuxiliaryNamesOptions]:
        if optional_auxiliary_names_model is None:
            return None

        return AuxiliaryNamesOptions(
            domain=optional_auxiliary_names_model.domain,
            use_for_rdns=optional_auxiliary_names_model.use_for_rdns,
            zone_ns_ips=tuple(optional_auxiliary_names_model.zone_ns_ips)
        )
