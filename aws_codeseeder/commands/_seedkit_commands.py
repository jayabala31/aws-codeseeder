#  Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License").
#    You may not use this file except in compliance with the License.
#    You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

from typing import Dict, List, Optional, Tuple

from boto3 import Session

from aws_codeseeder import LOGGER, _cfn_seedkit
from aws_codeseeder.services import cfn, s3


def seedkit_deployed(seedkit_name: str, session: Optional[Session] = None) -> Tuple[bool, str, Dict[str, str]]:
    """Checks for existence of the Seedkit CloudFormation Stack

    If the Stack exists, then the Stack Outputs are also returned to eliminate need for another roundtrip call to
    CloudFormation.

    Parameters
    ----------
    seedkit_name : str
        Named of the seedkit to check.
    session: Optional[Session], optional
        Optional Session to use for all boto3 operations, by default None

    Returns
    -------
    Tuple[bool, str, Dict[str, str]]
        Returns a Tuple with a bool indicating existence of the Stack, the Stack name, and a dict with the
        Stack Outputs
    """
    stack_name: str = cfn.get_stack_name(seedkit_name=seedkit_name)
    stack_exists, stack_outputs = cfn.does_stack_exist(stack_name=stack_name, session=session)
    return stack_exists, stack_name, stack_outputs


def deploy_seedkit(
    seedkit_name: str,
    managed_policy_arns: Optional[List[str]] = None,
    deploy_codeartifact: bool = False,
    session: Optional[Session] = None,
) -> None:
    """Deploys the seedkit resources into the environment.

    Resources deployed include: S3 Bucket, CodeArtifact Domain, CodeArtifact Repository, CodeBuild Project,
    IAM Role, IAM Managed Policy, and KMS Key. All resource names will include the seedkit_name and IAM Role and Policy
    grant least privilege access to only the resources associated with this Seedkit. Seedkits are deployed to an
    AWS Region, names on global resources (S3, IAM) include a region identifier to avoid conflicts and ensure the same
    Seedkit name can be deployed to multiple regions.

    Parameters
    ----------
    seedkit_name : str
        Name of the seedkit to deploy. All resources will include this in their naming conventions
    managed_policy_arns : Optional[List[str]]
        List of Managed Policy to ARNs to attach to the default IAM Role created and used
        by the CodeBuild Project
    deploy_codeartifact : bool
        Trigger optional deployment of CodeArtifact Domain and Repository for use by the Seedkit and
        its libraries
    session: Optional[Session], optional
        Optional Session to use for all boto3 operations, by default None
    """
    deploy_id: Optional[str] = None
    stack_exists, stack_name, stack_outputs = seedkit_deployed(seedkit_name=seedkit_name, session=session)
    LOGGER.info("Deploying Seedkit %s with Stack Name %s", seedkit_name, stack_name)
    LOGGER.debug("Managed Policy Arns: %s", managed_policy_arns)
    if stack_exists:
        deploy_id = stack_outputs.get("DeployId")
        LOGGER.info("Seedkit found with DeployId: %s", deploy_id)
    template_filename: str = _cfn_seedkit.synth(
        seedkit_name=seedkit_name,
        deploy_id=deploy_id,
        managed_policy_arns=managed_policy_arns,
        deploy_codeartifact=deploy_codeartifact,
        session=session,
    )
    cfn.deploy_template(
        stack_name=stack_name, filename=template_filename, seedkit_tag=f"codeseeder-{seedkit_name}", session=session
    )
    LOGGER.info("Seedkit Deployed")


def destroy_seedkit(seedkit_name: str, session: Optional[Session] = None) -> None:
    """Destroys the resources associated with the seedkit.

    Parameters
    ----------
    seedkit_name : str
        Name of the seedkit to destroy
    session: Optional[Session], optional
        Optional Session to use for all boto3 operations, by default None
    """
    stack_exists, stack_name, stack_outputs = seedkit_deployed(seedkit_name=seedkit_name, session=session)
    LOGGER.info("Destroying Seedkit %s with Stack Name %s", seedkit_name, stack_name)
    if stack_exists:
        seedkit_bucket = stack_outputs.get("Bucket")
        if seedkit_bucket:
            s3.delete_bucket(bucket=seedkit_bucket, session=session)
        cfn.destroy_stack(stack_name=stack_name, session=session)
        LOGGER.info("Seedkit Destroyed")
    else:
        LOGGER.warn("Seedkit/Stack does not exist")
