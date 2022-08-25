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


from typing import Final, Optional, TextIO
import os
import datetime
import queue
from get4for6.logger.LogFacilities import LogFacilities
from get4for6.logger._LoggerThread import _LoggerThread


class Logger:
    _LOG_QUEUE_SIZE: Final[int] = 1024
    _TIMESTAMP_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
    _LINE_SEPARATOR: Final[str] = os.linesep

    def __init__(self, log_to: TextIO, log_debug_messages_from: frozenset[str]):
        self._log_to: Final[TextIO] = log_to
        self._log_debug_messages_from: Final[frozenset[str]] = log_debug_messages_from

        self._thread: Optional[_LoggerThread] = None
        self._log_queue: Final[queue.Queue] = queue.Queue(self.__class__._LOG_QUEUE_SIZE)
        self._message_sequence_number: int = 1

    def __enter__(self):
        assert (self._thread is None)

        self._thread = _LoggerThread(self._log_queue, self._log_to)
        self._thread.start()
        self.debug("Logger thread has been started.", LogFacilities.LOGGER_START)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        assert (self._thread is not None)

        try:
            if not self._thread.is_alive():
                return  # The thread has already died

            self.debug("Logger thread is being stopped.", LogFacilities.LOGGER_STOP)
            self._log_queue.put(None)  # Signal the thread that we want to terminate it
            self._thread.join()
        finally:
            self._thread = None

    def warning(self, message: str, facility: str) -> None:
        if self._thread is None:
            return

        self._log("WARN", facility, message)

    def info(self, message: str, facility: str) -> None:
        if self._thread is None:
            return

        self._log("INFO", facility, message)

    def debug(self, message: str, facility: str) -> None:
        if self._thread is None:
            return

        if ("*" in self._log_debug_messages_from) or (facility in self._log_debug_messages_from):
            self._log("DEBUG", facility, message)

    def _log(self, level: str, facility: str, message: str) -> None:
        current_timestamp = datetime.datetime.now().strftime(self.__class__._TIMESTAMP_FORMAT)
        logged_line = f"[{current_timestamp} / {self._message_sequence_number} / {level} / {facility}] {message}"

        self._message_sequence_number += 1

        self.write_line_nonblock(logged_line)

    def write_line_nonblock(self, written_line: str) -> None:
        if self._thread is None:
            return

        try:
            self._log_queue.put_nowait(written_line + self.__class__._LINE_SEPARATOR)
        except queue.Full:
            pass  # If the 'log_to' queue is clogged, strings are silently discarded when putting them there in non-blocking mode

    def write_line_block(self, written_line: str) -> None:
        if self._thread is None:
            return

        self._log_queue.put(written_line + self.__class__._LINE_SEPARATOR)
