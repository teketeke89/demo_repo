import time
import os
import json
import boto3
from botocore.exceptions import ClientError

SHARED_SERVICES = 'Shared Services'
TENANTS = 'Tenants'


def get_parent_id(org_client):
    response = org_client.list_roots()
    for root in response['Roots']:
        root_id = root['Id']
        break
    return root_id


def organization_exists(org_client):
    try:
        org_client.describe_organization()
        return True
    except ClientError:
        pass
    return False


def verify_organization(org_client):
    class InvalidOrganizationalUnitsException(Exception):
        pass

    root_id = get_parent_id(org_client)
    print(root_id)

    response = org_client.list_organizational_units_for_parent(
        ParentId=root_id
    )
    print(response)

    organizational_units = response['OrganizationalUnits']

    print(organizational_units)

    if (len(organizational_units) != 2):
        raise InvalidOrganizationalUnitsException()

    has_shared_services_ou = False
    has_tenants_ou = False
    for organizational_unit in organizational_units:
        if organizational_unit['Name'] == SHARED_SERVICES:
            has_shared_services_ou = True
        elif organizational_unit['Name'] == TENANTS:
            has_tenants_ou = True

    if (not has_shared_services_ou or not has_tenants_ou):
        raise InvalidOrganizationalUnitsException()


def initialize_organization(org_client):
    org_client.create_organization(
        FeatureSet='ALL'
    )
    root_id = get_parent_id(org_client)
    org_client.create_organizational_unit(
        ParentId=root_id,
        Name=SHARED_SERVICES
    )
    org_client.create_organizational_unit(
        ParentId=root_id,
        Name=TENANTS
    )


def main():
    ssm_client = boto3.client('ssm')

    govcloud_access_key_id = ssm_client.get_parameter(
        Name='/accounts/aws-us-gov/access-key-id'
    )['Parameter']['Value']
    govcloud_secret_access_key = ssm_client.get_parameter(
        Name='/accounts/aws-us-gov/secret-access-key',
        WithDecryption=True
    )['Parameter']['Value']
    govcloud_region = 'us-gov-west-1'

    org_client_std = boto3.client('organizations')
    org_client_gc = boto3.client('organizations',
                                aws_access_key_id=govcloud_access_key_id,
                                aws_secret_access_key=govcloud_secret_access_key,
                                region_name=govcloud_region)

    if (organization_exists(org_client_std)):
        verify_organization(org_client_std)
        verify_organization(org_client_gc)
    else:
        initialize_organization(org_client_gc)
        initialize_organization(org_client_std)

    ssm_client_gc = boto3.client('ssm',
                                aws_access_key_id=govcloud_access_key_id,
                                aws_secret_access_key=govcloud_secret_access_key,
                                region_name=govcloud_region)

    response = org_client_gc.describe_organization()
    organization_id = response['Organization']['Id']

    ssm_client_gc.put_parameter(
        Name='/core/organization/id',
        Value=organization_id,
        Type='String',
        Overwrite=True
    )

    return {}
main()