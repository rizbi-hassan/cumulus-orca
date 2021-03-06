"""
Name: test_request_files.py

Description:  Unit tests for request_files.py.
"""
import os
import unittest
import uuid
from random import randint, uniform
from unittest import mock
from unittest.mock import patch, MagicMock, call, Mock

# noinspection PyPackageRequirements
# noinspection PyPackageRequirements
import database
import requests_db
# noinspection PyPackageRequirements
from botocore.exceptions import ClientError
# noinspection PyPackageRequirements
from database import DbError

import request_files
from test.request_helpers import (REQUEST_GROUP_ID_EXP_1, REQUEST_GROUP_ID_EXP_2,
                             REQUEST_GROUP_ID_EXP_3, REQUEST_ID1, REQUEST_ID2,
                             REQUEST_ID3, REQUEST_ID4, LambdaContextMock,
                             create_handler_event, create_insert_request,
                             mock_secretsmanager_get_parameter)

UTC_NOW_EXP_1 = requests_db.get_utc_now_iso()
FILE1 = "MOD09GQ___006/2017/MOD/MOD09GQ.A0219114.N5aUCG.006.0656338553321.h5"
FILE2 = "MOD09GQ___006/MOD/MOD09GQ.A0219114.N5aUCG.006.0656338553321.h5.met"
FILE3 = "MOD09GQ___006/MOD/MOD09GQ.A0219114.N5aUCG.006.0656338553321_ndvi.jpg"
FILE4 = "MOD09GQ___006/MOD/MOD09GQ.A0219114.N5aUCG.006.0656338553321.cmr.xml"
PROTECTED_BUCKET = "sndbx-cumulus-protected"
PUBLIC_BUCKET = "sndbx-cumulus-public"
KEY1 = {"key": FILE1, "dest_bucket": PROTECTED_BUCKET}
KEY2 = {"key": FILE2, "dest_bucket": PROTECTED_BUCKET}
KEY3 = {"key": FILE3, "dest_bucket": None}
KEY4 = {"key": FILE4, "dest_bucket": PUBLIC_BUCKET}


class TestRequestFiles(unittest.TestCase):
    """
    TestRequestFiles.
    """

    def setUp(self):
        # todo: single_query is not called in code. Replace with higher-level checks.
        self.mock_single_query = database.single_query
        # todo: These values should NOT be hard-coded as present for every test.
        os.environ["DATABASE_HOST"] = "my.db.host.gov"
        os.environ["DATABASE_PORT"] = "54"
        os.environ["DATABASE_NAME"] = "sndbx"
        os.environ["DATABASE_USER"] = "unittestdbuser"
        os.environ["DATABASE_PW"] = "unittestdbpw"
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = '5'
        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = '2'
        os.environ['PREFIX'] = uuid.uuid4().__str__()
        self.context = LambdaContextMock()

    def tearDown(self):
        database.single_query = self.mock_single_query
        os.environ.pop('PREFIX', None)
        os.environ.pop(request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY, None)
        os.environ.pop(request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY, None)
        os.environ.pop(request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY, None)
        os.environ.pop(request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY, None)
        del os.environ["DATABASE_HOST"]
        del os.environ["DATABASE_NAME"]
        del os.environ["DATABASE_USER"]
        del os.environ["DATABASE_PW"]
        del os.environ["DATABASE_PORT"]

    @patch('request_files.inner_task')
    def test_task_happy_path(self,
                             mock_inner_task: MagicMock):
        """
        All variables present and valid.
        """
        mock_event = Mock()
        max_retries = randint(0, 99999)
        retry_sleep_secs = uniform(0, 99999)
        retrieval_type = 'Bulk'
        exp_days = randint(0, 99999)

        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = max_retries.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY] = retry_sleep_secs.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY] = retrieval_type
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = exp_days.__str__()

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(mock_event, max_retries, retry_sleep_secs, retrieval_type, exp_days)

    @patch('request_files.inner_task')
    def test_task_default_for_missing_max_retries(self,
                                                  mock_inner_task: MagicMock):
        mock_event = Mock()
        retry_sleep_secs = uniform(0, 99999)
        retrieval_type = 'Bulk'
        exp_days = randint(0, 99999)

        os.environ[request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY] = retry_sleep_secs.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY] = retrieval_type
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = exp_days.__str__()

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(
            mock_event, request_files.DEFAULT_MAX_REQUEST_RETRIES, retry_sleep_secs, retrieval_type, exp_days)

    @patch('request_files.inner_task')
    def test_task_default_for_missing_sleep_secs(self,
                                                 mock_inner_task: MagicMock):
        mock_event = Mock()
        max_retries = randint(0, 99999)
        retrieval_type = 'Bulk'
        exp_days = randint(0, 99999)

        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = max_retries.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY] = retrieval_type
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = exp_days.__str__()

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(
            mock_event, max_retries, request_files.DEFAULT_RESTORE_RETRY_SLEEP_SECS, retrieval_type, exp_days)

    @patch('request_files.inner_task')
    def test_task_default_for_missing_retrieval_type(self,
                                                     mock_inner_task: MagicMock):
        mock_event = Mock()
        max_retries = randint(0, 99999)
        retry_sleep_secs = uniform(0, 99999)
        exp_days = randint(0, 99999)

        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = max_retries.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY] = retry_sleep_secs.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = exp_days.__str__()

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(
            mock_event, max_retries, retry_sleep_secs, request_files.DEFAULT_RESTORE_RETRIEVAL_TYPE, exp_days)

    @patch('request_files.inner_task')
    def test_task_default_for_bad_retrieval_type(self,
                                                 mock_inner_task: MagicMock):
        mock_event = Mock()
        max_retries = randint(0, 99999)
        retry_sleep_secs = uniform(0, 99999)
        retrieval_type = 'Nope'
        exp_days = randint(0, 99999)

        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = max_retries.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY] = retry_sleep_secs.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY] = retrieval_type
        os.environ[request_files.OS_ENVIRON_RESTORE_EXPIRE_DAYS_KEY] = exp_days.__str__()

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(
            mock_event, max_retries, retry_sleep_secs, request_files.DEFAULT_RESTORE_RETRIEVAL_TYPE, exp_days)

    @patch('request_files.inner_task')
    def test_task_default_for_missing_exp_days(self,
                                               mock_inner_task: MagicMock):
        """
        All variables present and valid.
        """
        mock_event = Mock()
        max_retries = randint(0, 99999)
        retry_sleep_secs = uniform(0, 99999)
        retrieval_type = 'Bulk'

        os.environ[request_files.OS_ENVIRON_RESTORE_REQUEST_RETRIES_KEY] = max_retries.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRY_SLEEP_SECS_KEY] = retry_sleep_secs.__str__()
        os.environ[request_files.OS_ENVIRON_RESTORE_RETRIEVAL_TYPE_KEY] = retrieval_type

        request_files.task(mock_event, None)

        mock_inner_task.assert_called_once_with(
            mock_event, max_retries, retry_sleep_secs, retrieval_type, request_files.DEFAULT_RESTORE_EXPIRE_DAYS)

    def test_inner_task_missing_glacier_bucket_raises(self):
        try:
            request_files.inner_task({request_files.EVENT_CONFIG_KEY: dict()},
                                     randint(0, 99999), randint(0, 99999), uuid.uuid4().__str__(), randint(0, 99999))
            self.fail('Error not raised.')
        except request_files.RestoreRequestError:
            pass

    @patch('request_files.process_granule')
    @patch('request_files.object_exists')
    @patch('boto3.client')
    def test_inner_task_missing_files_do_not_halt(self,
                                                  mock_boto3_client: MagicMock,
                                                  mock_object_exists: MagicMock,
                                                  mock_process_granule: MagicMock):
        """
        A return of 'false' from object_exists should ignore the file and continue.
        """
        glacier_bucket = uuid.uuid4().__str__()
        file_key_0 = uuid.uuid4().__str__()
        file_key_1 = uuid.uuid4().__str__()
        missing_file_key = uuid.uuid4().__str__()
        file_dest_bucket_0 = uuid.uuid4().__str__()
        file_dest_bucket_1 = uuid.uuid4().__str__()
        missing_file_dest_bucket = uuid.uuid4().__str__()
        file_0 = {
            request_files.FILE_KEY_KEY: file_key_0,
            request_files.FILE_DEST_BUCKET_KEY: file_dest_bucket_0
        }
        expected_file0_output = file_0.copy()
        expected_file0_output[request_files.FILE_SUCCESS_KEY] = False
        expected_file0_output[request_files.FILE_ERROR_MESSAGE_KEY] = ''
        file_1 = {
            request_files.FILE_KEY_KEY: file_key_1,
            request_files.FILE_DEST_BUCKET_KEY: file_dest_bucket_1
        }
        expected_file1_output = file_1.copy()
        expected_file1_output[request_files.FILE_SUCCESS_KEY] = False
        expected_file1_output[request_files.FILE_ERROR_MESSAGE_KEY] = ''
        expected_input_granule_files = [expected_file0_output, expected_file1_output]
        granule = {
            request_files.GRANULE_KEYS_KEY: [
                file_0,
                {
                    request_files.FILE_KEY_KEY: missing_file_key,
                    request_files.FILE_DEST_BUCKET_KEY: missing_file_dest_bucket
                },
                file_1
            ]
        }
        expected_input_granule = granule.copy()
        expected_input_granule[request_files.GRANULE_RECOVER_FILES_KEY] = expected_input_granule_files
        event = {
            request_files.EVENT_CONFIG_KEY: {
                request_files.CONFIG_GLACIER_BUCKET_KEY: glacier_bucket
            },
            request_files.EVENT_INPUT_KEY: {
                request_files.INPUT_GRANULES_KEY: [
                    granule
                ]
            }
        }
        max_retries = randint(0, 99999)
        retry_sleep_secs = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        mock_s3_cli = mock_boto3_client('s3')

        def object_exists_return_func(input_s3_cli, input_glacier_bucket, input_file_key):
            return input_file_key in [file_key_0, file_key_1]

        mock_object_exists.side_effect = object_exists_return_func

        result = request_files.inner_task(event, max_retries, retry_sleep_secs, retrieval_type, restore_expire_days)
        mock_process_granule.assert_has_calls([
            call(mock_s3_cli, expected_input_granule, glacier_bucket, restore_expire_days, max_retries,
                 retry_sleep_secs, retrieval_type)])
        self.assertEqual(1, mock_process_granule.call_count)  # I'm hoping that we can remove the 'one granule' limit.
        self.assertEqual({request_files.INPUT_GRANULES_KEY: [expected_input_granule]}, result)

    @patch('requests_db.request_id_generator')
    @patch('time.sleep')
    @patch('request_files.restore_object')
    def test_process_granule_minimal_path(self,
                                          mock_restore_object: MagicMock,
                                          mock_sleep: MagicMock,
                                          mock_request_id_generator: MagicMock):
        mock_s3 = Mock()
        max_retries = randint(10, 999)
        glacier_bucket = uuid.uuid4().__str__()
        retry_sleep_secs = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        granule_id = uuid.uuid4().__str__()
        request_group_id = uuid.uuid4().__str__()
        file_name_0 = uuid.uuid4().__str__()
        dest_bucket_0 = uuid.uuid4().__str__()
        file_name_1 = uuid.uuid4().__str__()
        dest_bucket_1 = uuid.uuid4().__str__()

        mock_request_id_generator.return_value = request_group_id

        granule = {
            request_files.GRANULE_GRANULE_ID_KEY: granule_id,
            request_files.GRANULE_RECOVER_FILES_KEY: [
                {
                    request_files.FILE_KEY_KEY: file_name_0,
                    request_files.FILE_DEST_BUCKET_KEY: dest_bucket_0,
                    request_files.FILE_SUCCESS_KEY: False,
                    request_files.FILE_ERROR_MESSAGE_KEY: ''
                },
                {
                    request_files.FILE_KEY_KEY: file_name_1,
                    request_files.FILE_DEST_BUCKET_KEY: dest_bucket_1,
                    request_files.FILE_SUCCESS_KEY: False,
                    request_files.FILE_ERROR_MESSAGE_KEY: ''
                }
            ]
        }

        request_files.process_granule(mock_s3, granule, glacier_bucket, restore_expire_days, max_retries,
                                      retry_sleep_secs, retrieval_type)

        self.assertTrue(granule[request_files.GRANULE_RECOVER_FILES_KEY][0][request_files.FILE_SUCCESS_KEY])
        self.assertTrue(granule[request_files.GRANULE_RECOVER_FILES_KEY][1][request_files.FILE_SUCCESS_KEY])
        mock_restore_object.assert_has_calls([
            call(
                mock_s3,
                {
                    request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                    request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                    request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                    'key': file_name_0,  # This property isn't from anything besides this code.
                    request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                    'days': restore_expire_days  # This property isn't from anything besides this code.
                },
                1,
                max_retries,
                retrieval_type
            ),
            call(
                mock_s3,
                {
                    request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                    request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                    request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                    'key': file_name_1,  # This property isn't from anything besides this code.
                    request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_1,
                    'days': restore_expire_days  # This property isn't from anything besides this code.
                },
                1,
                max_retries,
                retrieval_type
            )
        ])
        self.assertEqual(2, mock_restore_object.call_count)
        mock_request_id_generator.assert_called_once_with()
        mock_sleep.assert_not_called()

    @patch('requests_db.request_id_generator')
    @patch('time.sleep')
    @patch('request_files.restore_object')
    def test_process_granule_one_client_error_retries(self,
                                                      mock_restore_object: MagicMock,
                                                      mock_sleep: MagicMock,
                                                      mock_request_id_generator: MagicMock):
        mock_s3 = Mock()
        max_retries = 5
        glacier_bucket = uuid.uuid4().__str__()
        retry_sleep_secs = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        granule_id = uuid.uuid4().__str__()
        request_group_id = uuid.uuid4().__str__()
        file_name_0 = uuid.uuid4().__str__()
        dest_bucket_0 = uuid.uuid4().__str__()

        mock_request_id_generator.return_value = request_group_id

        granule = {
            request_files.GRANULE_GRANULE_ID_KEY: granule_id,
            request_files.GRANULE_RECOVER_FILES_KEY: [
                {
                    request_files.FILE_KEY_KEY: file_name_0,
                    request_files.FILE_DEST_BUCKET_KEY: dest_bucket_0,
                    request_files.FILE_SUCCESS_KEY: False,
                    request_files.FILE_ERROR_MESSAGE_KEY: ''
                }
            ]
        }

        mock_restore_object.side_effect = [ClientError({}, ''), None]

        request_files.process_granule(mock_s3, granule, glacier_bucket, restore_expire_days, max_retries,
                                      retry_sleep_secs, retrieval_type)

        self.assertTrue(granule[request_files.GRANULE_RECOVER_FILES_KEY][0][request_files.FILE_SUCCESS_KEY])
        mock_restore_object.assert_has_calls([
            call(
                mock_s3,
                {
                    request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                    request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                    request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                    'key': file_name_0,  # This property isn't from anything besides this code.
                    request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                    'days': restore_expire_days  # This property isn't from anything besides this code.
                },
                1,
                max_retries,
                retrieval_type
            ),
            call(
                mock_s3,
                {
                    request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                    request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                    request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                    'key': file_name_0,  # This property isn't from anything besides this code.
                    request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                    'days': restore_expire_days  # This property isn't from anything besides this code.
                },
                2,
                max_retries,
                retrieval_type
            )
        ])
        self.assertEqual(2, mock_restore_object.call_count)
        mock_request_id_generator.assert_called_once_with()
        mock_sleep.assert_called_once_with(retry_sleep_secs)

    @patch('requests_db.request_id_generator')
    @patch('time.sleep')
    @patch('request_files.restore_object')
    @patch('cumulus_logger.CumulusLogger.error')
    def test_process_granule_client_errors_retries_until_cap(self,
                                                             mock_logger_error: MagicMock,
                                                             mock_restore_object: MagicMock,
                                                             mock_sleep: MagicMock,
                                                             mock_request_id_generator: MagicMock):
        mock_s3 = Mock()
        max_retries = randint(3, 20)
        glacier_bucket = uuid.uuid4().__str__()
        retry_sleep_secs = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        granule_id = uuid.uuid4().__str__()
        request_group_id = uuid.uuid4().__str__()
        file_name_0 = uuid.uuid4().__str__()
        dest_bucket_0 = uuid.uuid4().__str__()

        mock_request_id_generator.return_value = request_group_id

        granule = {
            request_files.GRANULE_GRANULE_ID_KEY: granule_id,
            request_files.GRANULE_RECOVER_FILES_KEY: [
                {
                    request_files.FILE_KEY_KEY: file_name_0,
                    request_files.FILE_DEST_BUCKET_KEY: dest_bucket_0,
                    request_files.FILE_SUCCESS_KEY: False,
                    request_files.FILE_ERROR_MESSAGE_KEY: ''
                }
            ]
        }

        mock_restore_object.side_effect = ClientError({}, '')

        try:
            request_files.process_granule(mock_s3, granule, glacier_bucket, restore_expire_days, max_retries,
                                          retry_sleep_secs, retrieval_type)
            self.fail('Error not Raised.')
        except request_files.RestoreRequestError:
            self.assertFalse(granule[request_files.GRANULE_RECOVER_FILES_KEY][0][request_files.FILE_SUCCESS_KEY])
            mock_restore_object.assert_has_calls([
                call(
                    mock_s3,
                    {
                        request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                        request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                        request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                        'key': file_name_0,  # This property isn't from anything besides this code.
                        request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                        'days': restore_expire_days  # This property isn't from anything besides this code.
                    },
                    1,
                    max_retries,
                    retrieval_type
                ),
                call(
                    mock_s3,
                    {
                        request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                        request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                        request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                        'key': file_name_0,  # This property isn't from anything besides this code.
                        request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                        'days': restore_expire_days  # This property isn't from anything besides this code.
                    },
                    2,
                    max_retries,
                    retrieval_type
                ),
                call(
                    mock_s3,
                    {
                        request_files.REQUESTS_DB_REQUEST_GROUP_ID_KEY: request_group_id,
                        request_files.REQUESTS_DB_GRANULE_ID_KEY: granule_id,
                        request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
                        'key': file_name_0,  # This property isn't from anything besides this code.
                        request_files.REQUESTS_DB_DEST_BUCKET_KEY: dest_bucket_0,
                        'days': restore_expire_days  # This property isn't from anything besides this code.
                    },
                    3,
                    max_retries,
                    retrieval_type
                )
            ])
            self.assertEqual(max_retries + 1, mock_restore_object.call_count)
            mock_request_id_generator.assert_called_once_with()
            mock_sleep.assert_has_calls([call(retry_sleep_secs)] * max_retries)

    def test_object_exists_happy_path(self):
        mock_s3_cli = Mock()
        mock_s3_cli.head_object.side_effect = None
        glacier_bucket = uuid.uuid4().__str__()
        file_key = uuid.uuid4().__str__()

        result = request_files.object_exists(mock_s3_cli, glacier_bucket, file_key)
        self.assertTrue(result)

    def test_object_exists_client_error_raised(self):
        expected_error = ClientError({'Error': {'Code': 'Teapot'}}, '')
        mock_s3_cli = Mock()
        mock_s3_cli.head_object.side_effect = expected_error
        glacier_bucket = uuid.uuid4().__str__()
        file_key = uuid.uuid4().__str__()

        try:
            request_files.object_exists(mock_s3_cli, glacier_bucket, file_key)
            self.fail('Error not raised.')
        except ClientError as err:
            self.assertEqual(expected_error, err)

    def test_object_exists_NotFound_returns_false(self):
        expected_error = ClientError({'Error': {'Code': 'NotFound'}}, '')
        mock_s3_cli = Mock()
        mock_s3_cli.head_object.side_effect = expected_error
        glacier_bucket = uuid.uuid4().__str__()
        file_key = uuid.uuid4().__str__()

        result = request_files.object_exists(mock_s3_cli, glacier_bucket, file_key)
        self.assertFalse(result)

    @patch('requests_db.submit_request')
    @patch('cumulus_logger.CumulusLogger.info')
    @patch('requests_db.create_data')
    def test_restore_object_happy_path(self,
                                       mock_create_data: MagicMock,
                                       mock_logger_info: MagicMock,
                                       mock_submit_request: MagicMock):
        request_id = uuid.uuid4().__str__()
        glacier_bucket = uuid.uuid4().__str__()
        key = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        mock_s3_cli = Mock()

        mock_data = {request_files.REQUESTS_DB_REQUEST_ID_KEY: request_id}
        mock_create_data.return_value = mock_data

        obj = {
            request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
            'key': key,  # This property isn't from anything besides this code.
            'days': restore_expire_days  # This property isn't from anything besides this code.
        }

        mock_submit_request.side_effect = None

        request_files.restore_object(mock_s3_cli, obj, randint(0, 99999), randint(0, 99999), retrieval_type)

        mock_create_data.assert_called_once_with(obj, 'restore', 'inprogress', None, None)
        mock_s3_cli.restore_object.assert_called_once_with(Bucket=glacier_bucket,
                                                           Key=key,
                                                           RestoreRequest={
                                                               'Days': restore_expire_days,
                                                               'GlacierJobParameters': {
                                                                   'Tier': retrieval_type}})
        mock_submit_request.assert_called_once_with(mock_data)

    @patch('requests_db.submit_request')
    @patch('cumulus_logger.CumulusLogger.info')
    @patch('requests_db.create_data')
    def test_restore_object_client_error_raises(self,
                                                mock_create_data: MagicMock,
                                                mock_logger_info: MagicMock,
                                                mock_submit_request: MagicMock):
        request_id = uuid.uuid4().__str__()
        glacier_bucket = uuid.uuid4().__str__()
        key = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        expected_error = ClientError({}, '')
        mock_s3_cli = Mock()
        mock_s3_cli.restore_object.side_effect = expected_error

        mock_data = {request_files.REQUESTS_DB_REQUEST_ID_KEY: request_id}
        mock_create_data.return_value = mock_data

        obj = {
            request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
            'key': key,  # This property isn't from anything besides this code.
            'days': restore_expire_days  # This property isn't from anything besides this code.
        }

        try:
            request_files.restore_object(mock_s3_cli, obj, 1, 1, retrieval_type)
            self.fail('Error not Raised.')
        except ClientError as error:
            self.assertEqual(expected_error, error)
            mock_create_data.assert_called_once_with(obj, 'restore', 'inprogress', None, None)
            mock_s3_cli.restore_object.assert_called_once_with(Bucket=glacier_bucket,
                                                               Key=key,
                                                               RestoreRequest={
                                                                   'Days': restore_expire_days,
                                                                   'GlacierJobParameters': {
                                                                       'Tier': retrieval_type}})
            mock_submit_request.assert_not_called()

    @patch('cumulus_logger.CumulusLogger.error')
    @patch('requests_db.submit_request')
    @patch('cumulus_logger.CumulusLogger.info')
    @patch('requests_db.create_data')
    def test_restore_object_client_error_last_attempt_logs_and_raises(self,
                                                                      mock_create_data: MagicMock,
                                                                      mock_logger_info: MagicMock,
                                                                      mock_submit_request: MagicMock,
                                                                      mock_logger_error: MagicMock):
        request_id = uuid.uuid4().__str__()
        glacier_bucket = uuid.uuid4().__str__()
        key = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        expected_error = ClientError({}, '')
        mock_s3_cli = Mock()
        mock_s3_cli.restore_object.side_effect = expected_error

        mock_data = {request_files.REQUESTS_DB_REQUEST_ID_KEY: request_id}
        mock_create_data.return_value = mock_data

        mock_submit_request.side_effect = requests_db.DatabaseError()  # error while logging to database should NOT halt

        obj = {
            request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
            'key': key,  # This property isn't from anything besides this code.
            'days': restore_expire_days  # This property isn't from anything besides this code.
        }

        try:
            request_files.restore_object(mock_s3_cli, obj, 2, 1, retrieval_type)
            self.fail('Error not Raised.')
        except ClientError as error:
            self.assertEqual(expected_error, error)
            mock_create_data.assert_called_once_with(obj, 'restore', 'inprogress', None, None)
            mock_s3_cli.restore_object.assert_called_once_with(Bucket=glacier_bucket,
                                                               Key=key,
                                                               RestoreRequest={
                                                                   'Days': restore_expire_days,
                                                                   'GlacierJobParameters': {
                                                                       'Tier': retrieval_type}})
            mock_submit_request.assert_called_once_with({
                request_files.REQUESTS_DB_REQUEST_ID_KEY: request_id,
                request_files.FILE_ERROR_MESSAGE_KEY: mock.ANY,
                request_files.REQUESTS_DB_JOB_STATUS_KEY: 'error'
            })

    @patch('cumulus_logger.CumulusLogger.error')
    @patch('requests_db.submit_request')
    @patch('cumulus_logger.CumulusLogger.info')
    @patch('requests_db.create_data')
    def test_restore_object_log_to_db_fails_does_not_halt(self,
                                                          mock_create_data: MagicMock,
                                                          mock_logger_info: MagicMock,
                                                          mock_submit_request: MagicMock,
                                                          mock_logger_error: MagicMock):
        request_id = uuid.uuid4().__str__()
        glacier_bucket = uuid.uuid4().__str__()
        key = uuid.uuid4().__str__()
        restore_expire_days = randint(0, 99999)
        retrieval_type = uuid.uuid4().__str__()
        mock_s3_cli = Mock()

        mock_data = {request_files.REQUESTS_DB_REQUEST_ID_KEY: request_id}
        mock_create_data.return_value = mock_data

        obj = {
            request_files.REQUESTS_DB_GLACIER_BUCKET_KEY: glacier_bucket,
            'key': key,  # This property isn't from anything besides this code.
            'days': restore_expire_days  # This property isn't from anything besides this code.
        }

        mock_submit_request.side_effect = requests_db.DatabaseError()

        request_files.restore_object(mock_s3_cli, obj, randint(0, 99999), randint(0, 99999), retrieval_type)

        mock_create_data.assert_called_once_with(obj, 'restore', 'inprogress', None, None)
        mock_s3_cli.restore_object.assert_called_once_with(Bucket=glacier_bucket,
                                                           Key=key,
                                                           RestoreRequest={
                                                               'Days': restore_expire_days,
                                                               'GlacierJobParameters': {
                                                                   'Tier': retrieval_type}})
        mock_submit_request.assert_called_once_with(mock_data)

    # The below are legacy tests that don't strictly check request_files.py on its own. Remove/adjust as needed.
    @patch('cumulus_logger.CumulusLogger.error')
    def test_handler(self,
                     mock_logger_error: MagicMock):
        """
        Tests the handler
        # todo: Does it? How does it?
        """
        input_event = create_handler_event()
        task_input = {"input": input_event["payload"], "config": {}}
        exp_err = f'request: {task_input} does not contain a config value for glacier-bucket'
        try:
            request_files.handler(input_event, self.context)
            self.fail('Expected error not raised.')
        except request_files.RestoreRequestError as roe:
            self.assertEqual(exp_err, str(roe))

    @patch('requests_db.request_id_generator')
    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_one_granule_4_files_success(self,
                                              mock_logger_info: MagicMock,
                                              mock_boto3_client: MagicMock,
                                              mock_database_single_query: MagicMock,
                                              mock_request_id_generator: MagicMock):
        """
        Test four files for one granule - successful
        """
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        files = [KEY1, KEY2, KEY3, KEY4]
        input_event = {
            "input": {
                "granules": [
                    {
                        "granuleId": granule_id,
                        "keys": files
                    }
                ]
            },
            "config": {
                "glacier-bucket": "my-dr-fake-glacier-bucket"
            }
        }

        mock_s3_cli = mock_boto3_client('s3')
        mock_s3_cli.restore_object.side_effect = [None,
                                                  None,
                                                  None,
                                                  None
                                                  ]
        qresult_1_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, files[0],
            "restore", "some_bucket", "inprogress",
            UTC_NOW_EXP_1, None, None)
        qresult_2_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, files[1],
            "restore", "some_bucket", "inprogress",
            UTC_NOW_EXP_1, None, None)
        qresult_3_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, files[2],
            "restore", "some_bucket", "inprogress",
            UTC_NOW_EXP_1, None, None)
        qresult_4_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, files[3],
            "restore", "some_bucket", "inprogress",
            UTC_NOW_EXP_1, None, None)

        mock_request_id_generator.side_effect = [REQUEST_GROUP_ID_EXP_1,
                                                 REQUEST_ID1,
                                                 REQUEST_ID2,
                                                 REQUEST_ID3,
                                                 REQUEST_ID4]
        mock_database_single_query.side_effect = [qresult_1_inprogress, qresult_2_inprogress,
                                                  qresult_3_inprogress, qresult_4_inprogress]
        mock_secretsmanager_get_parameter(4)

        try:
            result = request_files.task(input_event, self.context)
        except requests_db.DatabaseError as err:
            self.fail(str(err))

        mock_boto3_client.assert_has_calls([call('secretsmanager')])
        mock_s3_cli.head_object.assert_any_call(Bucket='my-dr-fake-glacier-bucket',
                                                Key=FILE1)
        mock_s3_cli.head_object.assert_any_call(Bucket='my-dr-fake-glacier-bucket',
                                                Key=FILE2)
        mock_s3_cli.head_object.assert_any_call(Bucket='my-dr-fake-glacier-bucket',
                                                Key=FILE3)
        mock_s3_cli.head_object.assert_any_call(Bucket='my-dr-fake-glacier-bucket',
                                                Key=FILE4)
        restore_req_exp = {'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}}

        mock_s3_cli.restore_object.assert_any_call(
            Bucket='my-dr-fake-glacier-bucket',
            Key=FILE1,
            RestoreRequest=restore_req_exp)
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='my-dr-fake-glacier-bucket',
            Key=FILE2,
            RestoreRequest=restore_req_exp)
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='my-dr-fake-glacier-bucket',
            Key=FILE3,
            RestoreRequest=restore_req_exp)
        mock_s3_cli.restore_object.assert_called_with(
            Bucket='my-dr-fake-glacier-bucket',
            Key=FILE4,
            RestoreRequest=restore_req_exp)

        exp_gran = {
            'granuleId': granule_id,
            'keys': self.get_expected_keys(),
            'recover_files': self.get_expected_files()
        }
        exp_granules = {'granules': [exp_gran]}

        self.assertEqual(exp_granules, result)
        mock_database_single_query.assert_called()  # called 4 times # todo: No..?

    @staticmethod
    def get_expected_files():
        """
        builds a list of expected files
        """
        return [
            {'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''},
            {'key': FILE2, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''},
            {'key': FILE3, 'dest_bucket': None, 'success': True, 'err_msg': ''},
            {'key': FILE4, 'dest_bucket': PUBLIC_BUCKET, 'success': True, 'err_msg': ''}
        ]

    @staticmethod
    def get_expected_keys():
        """
        Builds a list of expected keys
        """
        return [
            {
                'dest_bucket': PROTECTED_BUCKET,
                'key': FILE1
            },
            {
                'dest_bucket': PROTECTED_BUCKET,
                'key': FILE2
            },
            {
                'dest_bucket': None,
                'key': FILE3
            },
            {
                'dest_bucket': PUBLIC_BUCKET,
                'key': FILE4
            },
        ]

    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('requests_db.request_id_generator')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.error')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_one_granule_1_file_db_error(self,
                                              mock_logger_info: MagicMock,
                                              mock_logger_error: MagicMock,
                                              mock_boto3_client: MagicMock,
                                              mock_request_id_generator: MagicMock,
                                              mock_database_single_query: MagicMock):
        """
        Test one file for one granule - db error inserting status
        """
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        input_event = {
            "input": {
                "granules": [
                    {
                        "granuleId": granule_id,
                        "keys": [
                            KEY1
                        ]
                    }
                ]
            },
            "config": {
                "glacier-bucket": "my-dr-fake-glacier-bucket"
            }
        }

        mock_s3_cli = mock_boto3_client('s3')
        mock_s3_cli.restore_object.side_effect = [None]
        mock_request_id_generator.side_effect = [REQUEST_GROUP_ID_EXP_1,
                                                 REQUEST_ID1]
        mock_database_single_query.side_effect = [DbError("mock insert failed error")]
        mock_secretsmanager_get_parameter(1)
        try:
            result = request_files.task(input_event, self.context)
        except requests_db.DatabaseError as err:
            self.fail(f"failed insert does not throw exception. {str(err)}")

        mock_boto3_client.assert_called_with('secretsmanager')
        mock_s3_cli.head_object.assert_any_call(Bucket='my-dr-fake-glacier-bucket',
                                                Key=FILE1)
        restore_req_exp = {'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}}
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='my-dr-fake-glacier-bucket',
            Key=FILE1,
            RestoreRequest=restore_req_exp)

        exp_granules = {'granules': [
            {
                'granuleId': granule_id,
                'keys': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET}],
                'recover_files': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''}]
            }
        ]}

        self.assertEqual(exp_granules, result)
        mock_database_single_query.assert_called()  # called 1 times

    def test_task_two_granules(self):
        """
        Test two granules with one file each - successful.
        """
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        exp_event = {"input": {
            "granules": [{"granuleId": granule_id,
                          "keys": [KEY1]},
                         {"granuleId": granule_id,
                          "keys": [KEY2]}]}, "config": {"glacier-bucket": "my-bucket"}}

        exp_err = "request_files can only accept 1 granule in the list. This input contains 2"
        try:
            request_files.task(exp_event, self.context)
            self.fail("RestoreRequestError expected")
        except request_files.RestoreRequestError as roe:
            self.assertEqual(exp_err, str(roe))

    @patch('requests_db.request_id_generator')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_file_not_in_glacier(self,
                                      mock_logger_info: MagicMock,
                                      mock_boto3_client: MagicMock,
                                      mock_request_id_generator: MagicMock):
        """
        Test a file that is not in glacier.
        # todo: Expand test descriptions.
        """
        file1 = "MOD09GQ___006/2017/MOD/MOD09GQ.A0219114.N5aUCG.006.0656338553321.xyz"
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        event = {
            'input': {
                "granules":
                    [{"granuleId": granule_id, "keys": [{"key": file1, "dest_bucket": None}]}]
            },
            "config": {"glacier-bucket": "my-bucket"}}
        mock_s3_cli = mock_boto3_client('s3')
        # todo: Verify the below with a real-world db. If not the same, fix request_files.object_exists
        mock_s3_cli.head_object.side_effect = [ClientError({'Error': {'Code': 'NotFound'}}, 'head_object')]
        mock_request_id_generator.return_value = REQUEST_GROUP_ID_EXP_1
        try:
            result = request_files.task(event, self.context)

            expected_granules = {
                'granules': [
                    {
                        'granuleId': granule_id,
                        'keys': [
                            {
                                'dest_bucket': None,
                                'key': file1
                            }
                        ],
                        'recover_files': []
                    }
                ]
            }
            self.assertEqual(expected_granules, result)
            mock_boto3_client.assert_called_with('s3')
            mock_s3_cli.head_object.assert_called_with(Bucket='my-bucket', Key=file1)
        except requests_db.DatabaseError as err:
            self.fail(str(err))  # todo: Why? If you let it throw, it ends up the same way.

    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('boto3.client')
    def test_task_no_retries_env_var(self,
                                     mock_boto3_client: MagicMock,
                                     mock_database_single_query: MagicMock):
        """
        Test environment var RESTORE_REQUEST_RETRIES not set - use default.
        """
        del os.environ['RESTORE_REQUEST_RETRIES']
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        # todo: Reduce string copy/paste for test values here and elsewhere.
        event = {
            "input": {
                "granules":
                    [{"granuleId": granule_id, "keys": [KEY1]}]}, "config": {"glacier-bucket": "some_bucket"}}

        mock_s3_cli = mock_boto3_client('s3')
        mock_s3_cli.restore_object.side_effect = [None]
        requests_db.request_id_generator.return_value = REQUEST_ID1

        exp_granules = {
            'granules': [
                {
                    'granuleId': granule_id,
                    'keys': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET}],
                    'recover_files': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''}]
                }
            ]
        }
        qresult_1_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, FILE1, "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        mock_database_single_query.side_effect = [qresult_1_inprogress]
        mock_secretsmanager_get_parameter(1)
        try:
            result = request_files.task(event, self.context)
            os.environ['RESTORE_REQUEST_RETRIES'] = '2'  # todo: This test claims 'no_retries'
            self.assertEqual(exp_granules, result)

            mock_boto3_client.assert_called_with('secretsmanager')
            mock_s3_cli.head_object.assert_called_with(Bucket='some_bucket',
                                                       Key=FILE1)
            restore_req_exp = {'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}}
            mock_s3_cli.restore_object.assert_called_with(
                Bucket='some_bucket',
                Key=FILE1,
                RestoreRequest=restore_req_exp)
            mock_database_single_query.assert_called_once()
        except request_files.RestoreRequestError as err:
            self.fail(str(err))  # todo: Why? If you let it throw, it ends up the same way.

    @patch('requests_db.request_id_generator')
    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_no_expire_days_env_var(self,
                                         mock_logger_info: MagicMock,
                                         mock_boto3_client: MagicMock,
                                         mock_database_single_query: MagicMock,
                                         mock_request_id_generator: MagicMock):
        """
        Test environment var RESTORE_EXPIRE_DAYS not set - use default.
        """
        del os.environ['RESTORE_EXPIRE_DAYS']
        os.environ['RESTORE_RETRIEVAL_TYPE'] = 'Expedited'
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        event = {
            "config": {"glacier-bucket": "some_bucket"},
            "input": {
                "granules": [{"granuleId": granule_id, "keys": [KEY1]}]
            }
        }

        mock_s3_cli = mock_boto3_client('s3')
        # mock_s3_cli.head_object = Mock()  # todo: Look into why this line was in many test without asserts.
        mock_s3_cli.restore_object.side_effect = [None]
        mock_request_id_generator.return_value = REQUEST_ID1
        exp_granules = {
            'granules': [
                {
                    'granuleId': granule_id,
                    'keys': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET}],
                    'recover_files': [{'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''}]
                }
            ]
        }

        qresult_1_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, FILE1, "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        mock_database_single_query.side_effect = [qresult_1_inprogress]
        mock_secretsmanager_get_parameter(1)

        try:
            result = request_files.task(event, self.context)
            self.assertEqual(exp_granules, result)
            os.environ['RESTORE_EXPIRE_DAYS'] = '3'
            del os.environ['RESTORE_RETRIEVAL_TYPE']
            mock_boto3_client.assert_called_with('secretsmanager')
            mock_s3_cli.head_object.assert_called_with(Bucket='some_bucket',
                                                       Key=FILE1)
            restore_req_exp = {'Days': 5, 'GlacierJobParameters': {'Tier': 'Expedited'}}
            mock_s3_cli.restore_object.assert_called_with(
                Bucket='some_bucket',
                Key=FILE1,
                RestoreRequest=restore_req_exp)
        except request_files.RestoreRequestError as err:
            self.fail(str(err))  # todo: Why? If you let it throw, it ends up the same way.
        mock_database_single_query.assert_called_once()

    @patch('cumulus_logger.CumulusLogger.error')
    def test_task_no_glacier_bucket(self,
                                    mock_logger_error: MagicMock):
        """
        Test for missing glacier-bucket in config.
        """
        exp_event = {"input": {
            "granules": [{"granuleId": "MOD09GQ.A0219114.N5aUCG.006.0656338553321",
                          "keys": [KEY1]}]}}

        exp_err = f"request: {exp_event} does not contain a config value for glacier-bucket"
        try:
            request_files.task(exp_event, self.context)
            self.fail("RestoreRequestError expected")
        except request_files.RestoreRequestError as err:
            self.assertEqual(exp_err, str(err))

    @patch('requests_db.request_id_generator')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.error')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_client_error_one_file(self,
                                        mock_logger_info: MagicMock,
                                        mock_logger_error: MagicMock,
                                        mock_boto3_client: MagicMock,
                                        mock_request_id_generator: MagicMock):
        """
        Test retries for restore error for one file.
        """
        exp_event = {"config": {"glacier-bucket": "some_bucket"}, "input": {
            "granules": [{"granuleId": "MOD09GQ.A0219114.N5aUCG.006.0656338553321",
                          "keys": [KEY1]}]}}

        os.environ['RESTORE_RETRY_SLEEP_SECS'] = '.5'  # todo: This is not reset between tests
        mock_request_id_generator.side_effect = [REQUEST_GROUP_ID_EXP_1,
                                                 REQUEST_ID1,
                                                 REQUEST_ID2,
                                                 REQUEST_ID3]
        mock_s3_cli = mock_boto3_client('s3')
        mock_s3_cli.restore_object.side_effect = [ClientError({'Error': {'Code': 'NoSuchBucket'}}, 'restore_object'),
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}}, 'restore_object'),
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}}, 'restore_object')]
        mock_secretsmanager_get_parameter(1)
        os.environ['RESTORE_RETRIEVAL_TYPE'] = 'Standard'  # todo: This is not reset between tests

        exp_gran = {
            'granuleId': 'MOD09GQ.A0219114.N5aUCG.006.0656338553321',
            'keys': [
                {
                    'key': FILE1,
                    'dest_bucket': PROTECTED_BUCKET
                }
            ],
            'recover_files': [
                {
                    'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': False,
                    'err_msg': 'An error occurred (NoSuchBucket) when calling the restore_object operation: Unknown'
                }
            ]
        }
        exp_err = f"One or more files failed to be requested. {exp_gran}"
        try:
            request_files.task(exp_event, self.context)
            self.fail("RestoreRequestError expected")
        except request_files.RestoreRequestError as err:
            self.assertEqual(exp_err, str(err))
        del os.environ['RESTORE_RETRY_SLEEP_SECS']
        del os.environ['RESTORE_RETRIEVAL_TYPE']
        mock_boto3_client.assert_called_with('secretsmanager')
        mock_s3_cli.head_object.assert_called_with(Bucket='some_bucket',
                                                   Key=FILE1)
        restore_req_exp = {'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}}
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='some_bucket',
            Key=FILE1,
            RestoreRequest=restore_req_exp)

    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('requests_db.request_id_generator')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.error')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_client_error_3_times(self,
                                       mock_logger_info: MagicMock,
                                       mock_logger_error: MagicMock,
                                       mock_boto3_client: MagicMock,
                                       mock_request_id_generator: MagicMock,
                                       mock_single_query: MagicMock):
        """
        Test three files, two successful, one errors on all retries and fails.
        """
        keys = [KEY1, KEY3, KEY4]

        exp_event = {"config": {"glacier-bucket": "some_bucket"}}
        gran = {"granuleId": "MOD09GQ.A0219114.N5aUCG.006.0656338553321", "keys": keys}

        exp_event["input"] = {
            "granules": [gran]}

        mock_request_id_generator.side_effect = [REQUEST_GROUP_ID_EXP_1,
                                                 REQUEST_ID1,
                                                 REQUEST_GROUP_ID_EXP_3,
                                                 REQUEST_ID2,
                                                 REQUEST_ID3,
                                                 REQUEST_ID4
                                                 ]
        mock_s3_cli = mock_boto3_client('s3')
        mock_s3_cli.restore_object.side_effect = [None,
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}},
                                                              'restore_object'),
                                                  None,
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}},
                                                              'restore_object'),
                                                  ClientError({'Error': {'Code': 'NoSuchKey'}},
                                                              'restore_object')
                                                  ]

        exp_gran = {
            'granuleId': gran["granuleId"],
            'keys': self.get_exp_keys_3_errs(),
            'recover_files': self.get_exp_files_3_errs()
        }
        exp_err = f"One or more files failed to be requested. {exp_gran}"
        qresult_1_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, gran["granuleId"], FILE1,
            "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        qresult_1_error, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, gran["granuleId"], FILE1,
            "restore", "some_bucket",
            "error", UTC_NOW_EXP_1, None, "'Code': 'NoSuchBucket'")
        qresult_3_inprogress, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_3, gran["granuleId"], FILE2,
            "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        qresult_3_error, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_3, gran["granuleId"], FILE2,
            "restore", "some_bucket",
            "error", UTC_NOW_EXP_1, None, "'Code': 'NoSuchBucket'")
        mock_single_query.side_effect = [qresult_1_inprogress,
                                         qresult_1_error,
                                         qresult_3_inprogress,
                                         qresult_1_error,
                                         qresult_3_error]
        mock_secretsmanager_get_parameter(5)
        try:
            request_files.task(exp_event, self.context)
            self.fail("RestoreRequestError expected")
        except request_files.RestoreRequestError as err:
            self.assertEqual(exp_err, str(err))

        mock_boto3_client.assert_called_with('secretsmanager')
        mock_s3_cli.head_object.assert_any_call(Bucket='some_bucket',
                                                Key=FILE1)
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='some_bucket',
            Key=FILE1,
            RestoreRequest={'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}})
        mock_single_query.assert_called()  # 5 times # todo: No..?

    @staticmethod
    def get_exp_files_3_errs():
        """
        builds list of expected files for test case
        """
        return [
            {'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''},
            {'key': FILE3, 'dest_bucket': None, 'success': False,
             'err_msg': 'An error occurred (NoSuchKey) when calling the restore_object '
                        'operation: Unknown'},
            {'key': FILE4, 'dest_bucket': PUBLIC_BUCKET, 'success': True, 'err_msg': ''}
        ]

    @staticmethod
    def get_exp_keys_3_errs():
        """
        builds list of expected files for test case
        """
        return [
            {'key': FILE1, 'dest_bucket': PROTECTED_BUCKET},
            {'key': FILE3, 'dest_bucket': None},
            {'key': FILE4, 'dest_bucket': PUBLIC_BUCKET}
        ]

    # todo: single_query is not called in code. Replace with higher-level checks.
    @patch('database.single_query')
    @patch('requests_db.request_id_generator')
    @patch('boto3.client')
    @patch('cumulus_logger.CumulusLogger.error')
    @patch('cumulus_logger.CumulusLogger.info')
    def test_task_client_error_2_times(self,
                                       mock_logger_info: MagicMock,
                                       mock_logger_error: MagicMock,
                                       mock_boto3_client: MagicMock,
                                       mock_request_id_generator: MagicMock,
                                       mock_database_single_query: MagicMock):
        """
        Test two files, first successful, second has two errors, then success.
        """
        exp_event = {"config": {"glacier-bucket": "some_bucket"}}
        gran = {}
        granule_id = "MOD09GQ.A0219114.N5aUCG.006.0656338553321"
        gran["granuleId"] = granule_id
        keys = [KEY1, KEY2]
        gran["keys"] = keys
        exp_event["input"] = {
            "granules": [gran]}
        mock_request_id_generator.side_effect = [REQUEST_GROUP_ID_EXP_1,
                                                 REQUEST_ID1,
                                                 REQUEST_GROUP_ID_EXP_2,
                                                 REQUEST_ID2,
                                                 REQUEST_ID3]
        mock_s3_cli = mock_boto3_client('s3')

        mock_s3_cli.restore_object.side_effect = [None,
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}},
                                                              'restore_object'),
                                                  ClientError({'Error': {'Code': 'NoSuchBucket'}},
                                                              'restore_object'),
                                                  None
                                                  ]

        exp_granules = {
            'granules': [
                {
                    'granuleId': granule_id,
                    'keys': [
                        {'key': FILE1, 'dest_bucket': PROTECTED_BUCKET},
                        {'key': FILE2, 'dest_bucket': PROTECTED_BUCKET}
                    ],
                    'recover_files': [
                        {'key': FILE1, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''},
                        {'key': FILE2, 'dest_bucket': PROTECTED_BUCKET, 'success': True, 'err_msg': ''}
                    ]
                }
            ]}

        qresult1, _ = create_insert_request(
            REQUEST_ID1, REQUEST_GROUP_ID_EXP_1, granule_id, keys[0], "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        qresult2, _ = create_insert_request(
            REQUEST_ID2, REQUEST_GROUP_ID_EXP_1, granule_id, keys[0], "restore", "some_bucket",
            "error", UTC_NOW_EXP_1, None, "'Code': 'NoSuchBucket'")
        qresult3, _ = create_insert_request(
            REQUEST_ID3, REQUEST_GROUP_ID_EXP_1, granule_id, keys[1], "restore", "some_bucket",
            "inprogress", UTC_NOW_EXP_1, None, None)
        mock_database_single_query.side_effect = [qresult1, qresult2, qresult2, qresult3]
        mock_secretsmanager_get_parameter(4)

        result = request_files.task(exp_event, self.context)
        self.assertEqual(exp_granules, result)

        mock_boto3_client.assert_has_calls([call('secretsmanager')])
        mock_s3_cli.restore_object.assert_any_call(
            Bucket='some_bucket',
            Key=FILE1,
            RestoreRequest={'Days': 5, 'GlacierJobParameters': {'Tier': 'Standard'}})
        mock_database_single_query.assert_called()  # 4 times # todo: No..?


if __name__ == '__main__':
    unittest.main(argv=['start'])
