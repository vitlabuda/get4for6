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


from typing import Final, Sequence
import ipaddress
from datalidator.validators.DefaultValidatorImplBase import DefaultValidatorImplBase
from datalidator.validators.impl.SequenceHasAllItemsUniqueValidator import SequenceHasAllItemsUniqueValidator
from datalidator.validators.impl.IPAddressIsInNetworkValidator import IPAddressIsInNetworkValidator
from get4for6.config.loader._TranslationConfigurationModel import _TranslationConfigurationModel
from get4for6.config.loader._IPNetworkSequenceHasNoOverlappingNetworksValidator import _IPNetworkSequenceHasNoOverlappingNetworksValidator
from get4for6.helpers.IPHelpers import IPHelpers


class _TranslationConfigurationValidator(DefaultValidatorImplBase[_TranslationConfigurationModel]):
    def __init__(self, tag: str = ""):
        DefaultValidatorImplBase.__init__(self, tag)

        self._all_items_unique_validator: Final[SequenceHasAllItemsUniqueValidator] = SequenceHasAllItemsUniqueValidator(tag=tag)  # Not necessary, but makes error messages more relevant
        self._no_overlapping_networks_validator: Final[_IPNetworkSequenceHasNoOverlappingNetworksValidator] = _IPNetworkSequenceHasNoOverlappingNetworksValidator(tag=tag)

    def _validate(self, data: _TranslationConfigurationModel) -> None:
        if (data.dynamic_substitute_addr_assigning is None) and (not data.static_substitute_addr_assignments):
            raise self._generate_data_validation_failed_exc("If dynamic substitute address assigning is turned off, there must be at least one static assignment configured!")

        # Exceptions are not caught here -> they propagate up the stack
        all_ipv4_subnets = (data.client_allowed_subnets + data.substitute_subnets)
        self._all_items_unique_validator.validate(all_ipv4_subnets)
        self._no_overlapping_networks_validator.validate(all_ipv4_subnets)

        not_in_network_validator = IPAddressIsInNetworkValidator(data.map_client_addrs_into, negate=True, tag=self._tag)
        for ipv4_address, ipv6_address in data.static_substitute_addr_assignments:
            self._check_if_static_substitute_ipv4_address_is_in_any_of_substitute_subnets(ipv4_address, data.substitute_subnets)
            not_in_network_validator.validate(ipv6_address)

    def _check_if_static_substitute_ipv4_address_is_in_any_of_substitute_subnets(self, static_substitute_ipv4_address: ipaddress.IPv4Address, substitute_subnets: Sequence[ipaddress.IPv4Network]) -> None:
        if not IPHelpers.is_ipv4_address_part_of_any_subnet(static_substitute_ipv4_address, substitute_subnets):
            raise self._generate_data_validation_failed_exc(f"The static substitute IPv4 address {static_substitute_ipv4_address} is not a part of any of the configured substitute subnets, or it is the network or the broadcast address of one!")
