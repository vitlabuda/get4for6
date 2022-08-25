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
from datalidator.blueprints.impl.IntegerBlueprint import IntegerBlueprint
from datalidator.blueprints.impl.TimeIntervalBlueprint import TimeIntervalBlueprint
from datalidator.validators.impl.SequenceIsNotEmptyValidator import SequenceIsNotEmptyValidator
from datalidator.validators.impl.IntegerIsPositiveValidator import IntegerIsPositiveValidator
from datalidator.validators.impl.NumberMinimumValueValidator import NumberMinimumValueValidator
from datalidator.validators.impl.NumberMaximumValueValidator import NumberMaximumValueValidator
from get4for6.config.loader._IPPortPairListBlueprint import _IPPortPairListBlueprint
from get4for6.config.loader._PassDictFurtherIfEnabledBlueprint import _PassDictFurtherIfEnabledBlueprint
from get4for6.config.loader._AuxiliaryNamesModel import _AuxiliaryNamesModel


class _DNSConfigurationModel(ObjectModel):
    listen_on = _IPPortPairListBlueprint(
        validators=(SequenceIsNotEmptyValidator(tag="listen_on"),),
        tag="listen_on"
    )
    max_simultaneous_queries = IntegerBlueprint(
        validators=(IntegerIsPositiveValidator(tag="max_simultaneous_queries"),),
        tag="max_simultaneous_queries"
    )
    tcp_communication_with_client_timeout = TimeIntervalBlueprint(
        validators=(
            NumberMinimumValueValidator(0.05, tag="tcp_communication_with_client_timeout"),  # 50 ms
            NumberMaximumValueValidator(5.0, tag="tcp_communication_with_client_timeout")
        ),
        tag="tcp_communication_with_client_timeout"
    )

    upstream_servers = _IPPortPairListBlueprint(tag="upstream_servers")
    upstream_query_timeout = TimeIntervalBlueprint(
        validators=(
            NumberMinimumValueValidator(0.1, tag="upstream_query_timeout"),  # 100 ms
            NumberMaximumValueValidator(10.0, tag="upstream_query_timeout")
        ),
        tag="upstream_query_timeout"
    )

    max_newly_assigned_substitute_addrs_per_response = IntegerBlueprint(
        validators=(IntegerIsPositiveValidator(tag="max_newly_assigned_substitute_addrs_per_response"),),
        tag="max_newly_assigned_substitute_addrs_per_response"
    )

    auxiliary_names = _PassDictFurtherIfEnabledBlueprint(
        pass_to_blueprint=ObjectBlueprint(
            _AuxiliaryNamesModel,
            tag="auxiliary_names"
        ),
        return_if_disabled=None,
        tag="auxiliary_names"
    )
