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


from typing import Final, TextIO
import queue
import threading


class _LoggerThread(threading.Thread):
    # Logging is done in a separate thread, as the main thread has work to do which is more important than waiting for
    #  a possibly clogged stream (e.g. a pipe leading to a slow SSH connection) until it accepts a string.
    # The option of implementing an asyncio-based logger was considered, but it is not viable as it would have to rely
    #  on direct watching of file descriptors and non-blocking writes, which do not work with some types of streams.

    def __init__(self, log_queue: queue.Queue, log_to: TextIO):
        threading.Thread.__init__(self, name="LoggerThread", daemon=True)

        self._log_queue: Final[queue.Queue] = log_queue
        self._log_to: Final[TextIO] = log_to

    # This method runs in the logger thread!
    def run(self) -> None:
        while True:
            logged_line = self._log_queue.get()

            if logged_line is None:  # This is a signal that we want to terminate
                break

            self._write_logged_line(logged_line)

    def _write_logged_line(self, logged_line: str) -> None:
        try:
            self._log_to.write(logged_line)
            self._log_to.flush()
        except (OSError, EOFError):
            pass  # It does not really matter if some log messages get lost due to errors
