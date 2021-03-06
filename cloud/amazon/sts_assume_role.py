#!/usr/bin/python
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

DOCUMENTATION = '''
---
module: sts_assume_role
short_description: Assume a role using AWS Security Token Service and obtain temporary credentials
description:
    - Assume a role using AWS Security Token Service and obtain temporary credentials
version_added: "2.X"
author: Andres Koetsier (@AKoetsier)
options:
  role_arn:
    description:
      - The Amazon Resource Name (ARN) of the role that the caller is assuming (http://docs.aws.amazon.com/IAM/latest/UserGuide/Using_Identifiers.html#Identifiers_ARNs)
    required: true
  role_session_name:
    description:
      - Name of the role's session - will be used by CloudTrail
    required: true
  policy:
    description:
      - Supplemental policy to use in addition to assumed role's policies.
    required: false
    default: null
  duration_seconds:
    description:
      - The duration, in seconds, of the role session. The value can range from 900 seconds (15 minutes) to 3600 seconds (1 hour). By default, the value is set to 3600 seconds.
    required: false
    default: null
  external_id:
    description:
      - A unique identifier that is used by third parties to assume a role in their customers' accounts.
    required: false
    default: null
  mfa_serial_number:
    description:
      - he identification number of the MFA device that is associated with the user who is making the AssumeRole call.
    required: false
    default: null
  mfa_token:
    description:
      - The value provided by the MFA device, if the trust policy of the role being assumed requires MFA.
    required: false
    default: null
notes:
  - In order to use the assumed role in a following playbook task you must pass the access_key, access_secret and access_token
extends_documentation_fragment:
    - aws
    - ec2
'''

EXAMPLES = '''
# Note: These examples do not set authentication details, see the AWS Guide for details.

# Assume an existing role (more details: http://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html)
sts_assume_role:
  role_arn: "arn:aws:iam::123456789012:role/someRole"
  role_session_name: "someRoleSession"
register: assumed_role

# Use the assumed role above to tag an instance in account 123456789012
ec2_tag:
  aws_access_key: "{{ assumed_role.sts_creds.access_key }}"
  aws_secret_key: "{{ assumed_role.sts_creds.secret_key }}"
  security_token: "{{ assumed_role.sts_creds.session_token }}"
  resource: i-xyzxyz01
  state: present
  tags:
    MyNewTag: value

'''

try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.ec2 import boto3_conn, ec2_argument_spec, get_aws_connection_info


def assume_role_policy(client, module):
    args = dict(
      RoleArn=module.params.get('role_arn'),
      RoleSessionName=module.params.get('role_session_name')
    )
    policy = module.params.get('policy')
    if policy is not None:
      args['Policy'] = policy

    duration_seconds = module.params.get('duration_seconds')
    if duration_seconds is not None:
      args['DurationSeconds'] = duration_seconds

    external_id = module.params.get('external_id')
    if external_id is not None:
      args['ExternalId'] = external_id

    mfa_serial_number = module.params.get('mfa_serial_number')
    if mfa_serial_number is not None:
      args['SerialNumber'] = mfa_serial_number

    mfa_token = module.params.get('mfa_token')
    if mfa_token is not None:
      args['TokenCode'] = mfa_token
    changed = False

    try:
        assumed_role = client.assume_role(**args)
        changed = True
    except ClientError as e:
        module.fail_json(msg=e)

    sts_creds = dict(
      access_key=assumed_role['Credentials']['AccessKeyId'],
      secret_key=assumed_role['Credentials']['SecretAccessKey'],
      session_token=assumed_role['Credentials']['SessionToken'],
      expiration=assumed_role['Credentials']['Expiration']
    )
    sts_user = dict(
      arn=assumed_role['AssumedRoleUser']['Arn'],
      assume_role_id=assumed_role['AssumedRoleUser']['AssumedRoleId']
    )

    module.exit_json(changed=changed, sts_creds=sts_creds, sts_user=sts_user)

def main():
    argument_spec = ec2_argument_spec()
    argument_spec.update(
        dict(
            role_arn = dict(required=True, default=None),
            role_session_name = dict(required=True, default=None),
            duration_seconds = dict(required=False, default=None, type='int'),
            external_id = dict(required=False, default=None),
            policy = dict(required=False, default=None),
            mfa_serial_number = dict(required=False, default=None),
            mfa_token = dict(required=False, default=None)
        )
    )

    module = AnsibleModule(argument_spec=argument_spec)

    if not HAS_BOTO3:
        module.fail_json(msg='boto3 required for this module')

    region, ec2_url, aws_connect_kwargs = get_aws_connection_info(module, boto3=True)

    if region:
        try:
            client = boto3_conn(module, conn_type='client', resource='sts', region=region, endpoint=ec2_url, **aws_connect_kwargs)
        except ClientError as e:
            module.fail_json(msg=str(e))
    else:
        module.fail_json(msg="region must be specified")

    try:
        assume_role_policy(client, module)
    except ClientError as e:
        module.fail_json(msg=e)


if __name__ == '__main__':
    main()
