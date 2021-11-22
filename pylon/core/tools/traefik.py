#!/usr/bin/python
# coding=utf-8
# pylint: disable=I0011

#   Copyright 2021 getcarrier.io
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
    Traefik tools
"""

import os
import socket

from redis import StrictRedis  # pylint: disable=E0401

from pylon.core import constants
from pylon.core.tools import log


def register_traefik_route(context):
    """ Create Traefik route for this Pylon instance """
    context.traefik_redis_keys = list()
    #
    if context.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        log.info("Running in development mode before reloader is started. Skipping registration")
        return
    #
    traefik_config = context.settings.get("traefik", dict())
    if not traefik_config:
        log.error("Cannot register route: no traefik config")
        return
    #
    redis_config = traefik_config.get("redis", dict())
    if not redis_config:
        log.error("Cannot register route: no redis config")
        return
    #
    local_hostname = socket.gethostname()
    local_port = context.settings.get("server", dict()).get("port", constants.SERVER_DEFAULT_PORT)
    #
    node_name = context.node_name
    #
    if "node_url" in traefik_config:
        node_url = traefik_config.get("node_url")
    elif "node_hostname" in traefik_config:
        node_url = f"http://{traefik_config.get('node_hostname')}:{local_port}"
    else:
        node_url = f"http://{local_hostname}:{local_port}"
    #
    log.info("Registering traefik route for node '%s'", node_name)
    #
    store = StrictRedis(
        host=redis_config.get("host", "localhost"),
        password=redis_config.get("password", None),
    )
    #
    traefik_rootkey = traefik_config.get("rootkey", "traefik")
    traefik_rule = traefik_config.get("rule", "PathPrefix(`/`)")
    traefik_entrypoint = traefik_config.get("entrypoint", "http")
    #
    store.set(f"{traefik_rootkey}/http/routers/{node_name}/rule", traefik_rule)
    store.set(f"{traefik_rootkey}/http/routers/{node_name}/entrypoints/0", traefik_entrypoint)
    store.set(f"{traefik_rootkey}/http/routers/{node_name}/service", f"{node_name}")
    store.set(f"{traefik_rootkey}/http/services/{node_name}/loadbalancer/servers/0/url", node_url)
    #
    context.traefik_redis_keys.append(f"{traefik_rootkey}/http/routers/{node_name}/rule")
    context.traefik_redis_keys.append(f"{traefik_rootkey}/http/routers/{node_name}/entrypoints/0")
    context.traefik_redis_keys.append(f"{traefik_rootkey}/http/routers/{node_name}/service")
    context.traefik_redis_keys.append(
        f"{traefik_rootkey}/http/services/{node_name}/loadbalancer/servers/0/url"
    )


def unregister_traefik_route(context):
    """ Delete Traefik route for this Pylon instance """
    #
    if context.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        log.info("Running in development mode before reloader is started. Skipping unregistration")
        return
    #
    traefik_config = context.settings.get("traefik", dict())
    if not traefik_config:
        log.error("Cannot unregister route: no traefik config")
        return
    #
    redis_config = traefik_config.get("redis", dict())
    if not redis_config:
        log.error("Cannot unregister route: no redis config")
        return
    #
    log.info("Unregistering traefik route for node '%s'", context.node_name)
    #
    store = StrictRedis(
        host=redis_config.get("host", "localhost"),
        password=redis_config.get("password", None),
    )
    #
    while context.traefik_redis_keys:
        key = context.traefik_redis_keys.pop()
        store.delete(key)