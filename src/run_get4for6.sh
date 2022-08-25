#!/bin/bash

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


# Variables
_GET4FOR6_SRC_DIRECTORY="$(dirname "$(realpath "$0")")"
_GET4FOR6_VIRTUALENV_DIRECTORY="${_GET4FOR6_SRC_DIRECTORY}/__venv__"
_GET4FOR6_REQUIREMENTS_FILE="${_GET4FOR6_SRC_DIRECTORY}/requirements.txt"
_GET4FOR6_MAIN_PYTHON_SCRIPT="${_GET4FOR6_SRC_DIRECTORY}/get4for6/get4for6.py"


# Functions
function _get4for6_exit_with_error() {
  local _ERROR_MESSAGE="$1"

  echo "# ERROR: ${_ERROR_MESSAGE}"
  exit 1
}

function _get4for6_print_info() {
  local _INFO_MESSAGE="$1"

  echo "# INFO: ${_INFO_MESSAGE}"
}


# Virtualenv
if [ -e "${_GET4FOR6_VIRTUALENV_DIRECTORY}" ]; then
  . "${_GET4FOR6_VIRTUALENV_DIRECTORY}/bin/activate" > /dev/null || _get4for6_exit_with_error "Failed to activate an already existing virtualenv!"
else
  _get4for6_print_info "Please wait until a new virtualenv is initialized for the program..."

  virtualenv -p python3 "${_GET4FOR6_VIRTUALENV_DIRECTORY}" > /dev/null || _get4for6_exit_with_error "Failed to create the new virtualenv!"
  . "${_GET4FOR6_VIRTUALENV_DIRECTORY}/bin/activate" > /dev/null || _get4for6_exit_with_error "Failed to activate the newly created virtualenv!"
  "${_GET4FOR6_VIRTUALENV_DIRECTORY}/bin/pip3" install -r "${_GET4FOR6_REQUIREMENTS_FILE}" > /dev/null || _get4for6_exit_with_error "Failed to install the program's dependencies into the newly created virtualenv!"

  _get4for6_print_info "The program's new virtualenv has been initialized successfully!"
fi


# Program launch
exec "${_GET4FOR6_VIRTUALENV_DIRECTORY}/bin/python3" -- "${_GET4FOR6_MAIN_PYTHON_SCRIPT}" "$@"
