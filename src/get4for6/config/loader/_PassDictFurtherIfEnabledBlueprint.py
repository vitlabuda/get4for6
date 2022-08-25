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


from typing import Final, TypeVar, Union, Generic, Any, Dict
from datalidator.blueprints.BlueprintIface import BlueprintIface
from datalidator.blueprints.DefaultBlueprintImplBase import DefaultBlueprintImplBase
from datalidator.blueprints.impl.BooleanBlueprint import BooleanBlueprint
from datalidator.blueprints.impl.StringBlueprint import StringBlueprint
from datalidator.blueprints.impl.DictionaryBlueprint import DictionaryBlueprint
from datalidator.blueprints.impl.GenericBlueprint import GenericBlueprint
from datalidator.blueprints.exc.InvalidInputDataExc import InvalidInputDataExc


_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T = TypeVar("_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T")
_PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T = TypeVar("_PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T")


class _PassDictFurtherIfEnabledBlueprint(DefaultBlueprintImplBase[Union[_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T, _PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T]], Generic[_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T, _PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T]):
    def __init__(self,
                 pass_to_blueprint: BlueprintIface[_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T],
                 return_if_disabled: _PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T,  # Should be immutable!
                 enabled_dict_key: str = "enabled",
                 tag: str = ""):
        DefaultBlueprintImplBase.__init__(self, tag)

        self._pass_to_blueprint: Final[BlueprintIface[_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T]] = pass_to_blueprint
        self._return_if_disabled: Final[_PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T] = return_if_disabled
        self._enabled_dict_key: Final[str] = enabled_dict_key

        self._input_dict_blueprint: Final[DictionaryBlueprint] = DictionaryBlueprint(
            key_blueprint=StringBlueprint(tag=tag),
            value_blueprint=GenericBlueprint(tag=tag),
            tag=tag
        )
        self._enabled_boolean_blueprint: Final[BooleanBlueprint] = BooleanBlueprint(tag=tag)

    def _use(self, input_data: Any) -> Union[_PassDictFurtherIfEnabledBlueprint_PassToBlueprint_T, _PassDictFurtherIfEnabledBlueprint_ReturnIfDisabled_T]:
        # Exceptions are not caught here -> they propagate up the stack
        input_dict = self._input_dict_blueprint.use(input_data)
        enabled_boolean = self._extract_enabled_boolean_from_input_dict(input_dict, input_data)

        if enabled_boolean:
            return self._pass_to_blueprint.use(input_dict)  # The "enabled" item has been removed from the dictionary

        return self._return_if_disabled

    def _extract_enabled_boolean_from_input_dict(self, input_dict: Dict[str, Any], input_data: Any) -> bool:
        try:
            # The "enabled" item is removed from the dictionary
            enabled_raw = input_dict.pop(self._enabled_dict_key)
        except KeyError:
            raise InvalidInputDataExc(f"The key {repr(self._enabled_dict_key)} is not present in the input dictionary!", self._tag, input_data)

        # Exceptions are not caught here -> they propagate up the stack
        return self._enabled_boolean_blueprint.use(enabled_raw)
