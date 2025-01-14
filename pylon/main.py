#!/usr/bin/python3
# coding=utf-8
# pylint: disable=C0411,C0413

#   Copyright 2020-2021 getcarrier.io
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
    Project entry point
"""

#
# Before all other imports and code: patch standard library and other libraries to use async I/O
#

import os

CORE_DEVELOPMENT_MODE = os.environ.get("CORE_DEVELOPMENT_MODE", "").lower() in ["true", "yes"]

if not CORE_DEVELOPMENT_MODE:
    import gevent.monkey  # pylint: disable=E0401
    gevent.monkey.patch_all(thread=False, subprocess=False)
    #
    import psycogreen.gevent  # pylint: disable=E0401
    psycogreen.gevent.patch_psycopg()

#
# Normal imports and code below
#

import socket
import signal

import flask  # pylint: disable=E0401
import flask_restful  # pylint: disable=E0401

from pylon.core.tools import log
from pylon.core.tools import log_loki
from pylon.core.tools import module
from pylon.core.tools import event
from pylon.core.tools import seed
from pylon.core.tools import git
from pylon.core.tools import rpc
from pylon.core.tools import slot
from pylon.core.tools import server
from pylon.core.tools import session
from pylon.core.tools import traefik

from pylon.core.tools.signal import signal_sigterm
from pylon.core.tools.context import Context


def main():  # pylint: disable=R0912,R0914,R0915
    """ Entry point """
    # Register signal handling
    signal.signal(signal.SIGTERM, signal_sigterm)
    # Enable logging and say hello
    log.enable_logging()
    log.info("Starting plugin-based Carrier core")
    # Make context holder
    context = Context()
    # Save debug status
    context.debug = CORE_DEVELOPMENT_MODE
    # Load settings from seed
    log.info("Loading and parsing settings")
    context.settings = seed.load_settings()
    if not context.settings:
        log.error("Settings are empty or invalid. Exiting")
        os._exit(1)  # pylint: disable=W0212
    # Save global node name
    context.node_name = context.settings.get("server", dict()).get("name", socket.gethostname())
    # Enable Loki logging if requested in config
    log_loki.enable_loki_logging(context)
    # Make ModuleManager instance
    context.module_manager = module.ModuleManager(context)
    # Make EventManager instance
    context.event_manager = event.EventManager(context)
    # Add global URL prefix to context
    server.add_url_prefix(context)
    # Make app instance
    log.info("Creating Flask application")
    context.app = flask.Flask("pylon")
    # Make API instance
    log.info("Creating API instance")
    context.api = flask_restful.Api(context.app, catch_all_404s=True)
    # Make SocketIO instance
    log.info("Creating SocketIO instance")
    context.sio = server.create_socketio_instance(context)
    # Add dispatcher and proxy middlewares if needed
    server.add_middlewares(context)
    # Set application settings
    context.app.config["CONTEXT"] = context
    context.app.config.from_mapping(context.settings.get("application", dict()))
    # Enable server-side sessions
    session.init_flask_sessions(context)
    # Make RpcManager instance
    context.rpc_manager = rpc.RpcManager(context)
    # Make SlotManager instance
    context.slot_manager = slot.SlotManager(context)
    # Apply patches needed for pure-python git and providers
    git.apply_patches()
    # Load and initialize modules
    context.module_manager.init_modules()
    # Register Traefik route via Redis KV
    traefik.register_traefik_route(context)
    # Run WSGI server
    try:
        server.run_server(context)
    finally:
        log.info("WSGI server stopped")
        # Unregister traefik route
        traefik.unregister_traefik_route(context)
        # De-init modules
        context.module_manager.deinit_modules()
    # Exit
    log.info("Exiting")


if __name__ == "__main__":
    # Call entry point
    main()
