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


from datalidator.blueprints.extras.ObjectModel import ObjectModel
from datalidator.blueprints.impl.ObjectBlueprint import ObjectBlueprint
from datalidator.blueprints.impl.ListBlueprint import ListBlueprint
from datalidator.blueprints.impl.IPNetworkBlueprint import IPNetworkBlueprint
from datalidator.validators.impl.SequenceIsNotEmptyValidator import SequenceIsNotEmptyValidator
from datalidator.validators.impl.SequenceHasAllItemsUniqueValidator import SequenceHasAllItemsUniqueValidator
from get4for6.config.loader._StaticSubstituteAddrAssignmentBlueprint import _StaticSubstituteAddrAssignmentBlueprint
from get4for6.config.loader._IPNetworkSequenceHasNoOverlappingNetworksValidator import _IPNetworkSequenceHasNoOverlappingNetworksValidator
from get4for6.config.loader._IPNetworkIsIPv4Validator import _IPNetworkIsIPv4Validator
from get4for6.config.loader._IPNetworkIsIPv6Validator import _IPNetworkIsIPv6Validator
from get4for6.config.loader._IPNetworkIsUsableValidator import _IPNetworkIsUsableValidator
from get4for6.config.loader._IPNetworkHasSpecificPrefixLengthValidator import _IPNetworkHasSpecificPrefixLengthValidator
from get4for6.config.loader._StaticSubstituteAddrAssignmentSequenceValidator import _StaticSubstituteAddrAssignmentSequenceValidator
from get4for6.config.loader._PassDictFurtherIfEnabledBlueprint import _PassDictFurtherIfEnabledBlueprint
from get4for6.config.loader._DynamicSubstituteAddrAssigningModel import _DynamicSubstituteAddrAssigningModel


class _TranslationConfigurationModel(ObjectModel):
    client_allowed_subnets = ListBlueprint(
        item_blueprint=IPNetworkBlueprint(
            validators=(
                _IPNetworkIsIPv4Validator(tag="client_allowed_subnets"),
                _IPNetworkIsUsableValidator(tag="client_allowed_subnets")
            ),
            tag="client_allowed_subnets"
        ),
        validators=(
            SequenceIsNotEmptyValidator(tag="client_allowed_subnets"),
            SequenceHasAllItemsUniqueValidator(tag="client_allowed_subnets"),  # Not necessary, but makes error messages more relevant
            _IPNetworkSequenceHasNoOverlappingNetworksValidator(tag="client_allowed_subnets")
        ),
        tag="client_allowed_subnets"
    )

    map_client_addrs_into = IPNetworkBlueprint(
        validators=(
            _IPNetworkIsIPv6Validator(tag="map_client_addrs_into"),
            _IPNetworkIsUsableValidator(tag="map_client_addrs_into"),
            _IPNetworkHasSpecificPrefixLengthValidator(prefix_length=96, tag="map_client_addrs_into")
        ),
        tag="map_client_addrs_into"
    )

    substitute_subnets = ListBlueprint(
        item_blueprint=IPNetworkBlueprint(
            validators=(
                _IPNetworkIsIPv4Validator(tag="substitute_subnets"),
                _IPNetworkIsUsableValidator(tag="substitute_subnets")
            ),
            tag="substitute_subnets"
        ),
        validators=(
            SequenceIsNotEmptyValidator(tag="substitute_subnets"),
            SequenceHasAllItemsUniqueValidator(tag="substitute_subnets"),  # Not necessary, but makes error messages more relevant
            _IPNetworkSequenceHasNoOverlappingNetworksValidator(tag="substitute_subnets")
        ),
        tag="substitute_subnets"
    )

    static_substitute_addr_assignments = ListBlueprint(
        item_blueprint=_StaticSubstituteAddrAssignmentBlueprint(tag="static_substitute_addr_assignments"),
        validators=(
            _StaticSubstituteAddrAssignmentSequenceValidator(tag="static_substitute_addr_assignments"),
        ),
        tag="static_substitute_addr_assignments"
    )

    dynamic_substitute_addr_assigning = _PassDictFurtherIfEnabledBlueprint(
        pass_to_blueprint=ObjectBlueprint(
            _DynamicSubstituteAddrAssigningModel,
            tag="dynamic_substitute_addr_assigning"
        ),
        return_if_disabled=None,
        tag="dynamic_substitute_addr_assigning"
    )
