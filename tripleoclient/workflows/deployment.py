# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from __future__ import print_function

import pprint
import time
import uuid

from heatclient.common import event_utils

from tripleoclient import exceptions
from tripleoclient import utils

from tripleoclient.workflows import base


def deploy(clients, **workflow_input):

    workflow_client = clients.workflow_engine
    tripleoclients = clients.tripleoclient
    queue_name = workflow_input['queue_name']

    execution = base.start_workflow(
        workflow_client,
        'tripleo.deployment.v1.deploy_plan',
        workflow_input=workflow_input
    )

    with tripleoclients.messaging_websocket(queue_name) as ws:
        message = ws.wait_for_message(execution.id)
        assert message['status'] == "SUCCESS", pprint.pformat(message)


def deploy_and_wait(log, clients, stack, plan_name, verbose_level,
                    timeout=None):
    """Start the deploy and wait for it to finish"""

    workflow_input = {
        "container": plan_name,
        "queue_name": str(uuid.uuid4()),
    }

    if timeout is not None:
        workflow_input['timeout'] = timeout

    deploy(clients, **workflow_input)

    orchestration_client = clients.orchestration

    if stack is None:
        log.info("Performing Heat stack create")
        action = 'CREATE'
        marker = None
    else:
        log.info("Performing Heat stack update")
        # Make sure existing parameters for stack are reused
        # Find the last top-level event to use for the first marker
        events = event_utils.get_events(orchestration_client,
                                        stack_id=plan_name,
                                        event_args={'sort_dir': 'desc',
                                                    'limit': 1})
        marker = events[0].id if events else None
        action = 'UPDATE'

    time.sleep(10)
    verbose_events = verbose_level > 0
    create_result = utils.wait_for_stack_ready(
        orchestration_client, plan_name, marker, action, verbose_events)
    if not create_result:
        if stack is None:
            raise exceptions.DeploymentError("Heat Stack create failed.")
        else:
            raise exceptions.DeploymentError("Heat Stack update failed.")
