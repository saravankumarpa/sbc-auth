# Copyright © 2019 Province of British Columbia
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Tests for the Authorization service.

Test suite to ensure that the Authorization service routines are working as expected.
"""

import uuid

import pytest
from werkzeug.exceptions import HTTPException

from auth_api.services.authorization import Authorization, check_auth
from auth_api.utils.roles import MEMBER, OWNER, STAFF
from tests.utilities.factory_utils import (
    factory_affiliation_model, factory_entity_model, factory_membership_model, factory_org_model, factory_user_model)


def test_get_user_authorizations_for_entity(session):  # pylint:disable=unused-argument
    """Assert that user authorizations for entity is working."""
    user = factory_user_model()
    org = factory_org_model('TEST')
    membership = factory_membership_model(user.id, org.id)
    entity = factory_entity_model()
    factory_affiliation_model(entity.id, org.id)

    authorization = Authorization.get_user_authorizations_for_entity({
        'sub': str(user.keycloak_guid),
        'realm_access': {
            'roles': ['basic']
        }}, entity.business_identifier)
    assert authorization is not None
    assert authorization.get('orgMembership', None) == membership.membership_type_code

    # Test with invalid user
    authorization = Authorization.get_user_authorizations_for_entity({'sub': str(uuid.uuid4()), 'realm_access': {
        'roles': ['basic']
    }}, entity.business_identifier)
    assert authorization is not None
    assert authorization.get('orgMembership', None) is None

    # Test for passcode users
    authorization = Authorization.get_user_authorizations_for_entity(
        {'loginSource': 'PASSCODE', 'username': entity.business_identifier, 'realm_access': {
            'roles': ['basic']
        }},
        entity.business_identifier)

    assert authorization is not None
    assert authorization.get('orgMembership', None) == 'OWNER'

    # Test for passcode users with invalid username
    authorization = Authorization.get_user_authorizations_for_entity(
        {'loginSource': 'PASSCODE', 'username': 'INVALID', 'realm_access': {
            'roles': ['basic']
        }},
        entity.business_identifier)

    assert authorization is not None
    assert authorization.get('orgMembership', None) is None

    # Test for staff users
    authorization = Authorization.get_user_authorizations_for_entity(
        {'loginSource': '', 'realm_access': {'roles': ['staff']}},
        entity.business_identifier)

    assert authorization is not None
    assert authorization.get('orgMembership', None) is None


def test_get_user_authorizations(session):  # pylint:disable=unused-argument
    """Assert that listing all user authorizations is working."""
    user = factory_user_model()
    org = factory_org_model('TEST')
    membership = factory_membership_model(user.id, org.id)
    entity = factory_entity_model()
    factory_affiliation_model(entity.id, org.id)

    authorization = Authorization.get_user_authorizations(str(user.keycloak_guid))
    assert authorization is not None
    assert authorization['authorizations'][0].get('orgMembership', None) == membership.membership_type_code

    # Test with invalid user
    authorization = Authorization.get_user_authorizations(str(uuid.uuid4()))
    assert authorization is not None
    assert len(authorization['authorizations']) == 0


def test_check_auth(session):  # pylint:disable=unused-argument
    """Assert that check_auth is working as expected."""
    user = factory_user_model()
    org = factory_org_model('TEST')
    factory_membership_model(user.id, org.id)
    entity = factory_entity_model()
    factory_affiliation_model(entity.id, org.id)

    # Test for staff role
    check_auth({'realm_access': {'roles': ['staff']}, 'sub': str(user.keycloak_guid)}, one_of_roles=STAFF)
    # Test for owner role
    check_auth({'realm_access': {'roles': ['public']}, 'sub': str(user.keycloak_guid)}, one_of_roles=OWNER,
               business_identifier=entity.business_identifier)

    # Test for exception, check for auth if resource is available for STAFF users
    with pytest.raises(HTTPException) as excinfo:
        check_auth({'realm_access': {'roles': ['public']}, 'sub': str(user.keycloak_guid)}, one_of_roles=[STAFF],
                   business_identifier=entity.business_identifier)
        assert excinfo.exception.code == 403

    # Test auth where STAFF role is in disabled role list
    with pytest.raises(HTTPException) as excinfo:
        check_auth({'realm_access': {'roles': ['staff']}, 'sub': str(user.keycloak_guid)}, disabled_roles=[STAFF],
                   business_identifier=entity.business_identifier)
        assert excinfo.exception.code == 403

    # Test auth where STAFF role is exact match
    with pytest.raises(HTTPException) as excinfo:
        check_auth({'realm_access': {'roles': ['public']}, 'sub': str(user.keycloak_guid)}, equals_role=MEMBER,
                   business_identifier=entity.business_identifier)
        assert excinfo.exception.code == 403