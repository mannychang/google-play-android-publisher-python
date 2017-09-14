#!/usr/bin/python
# -*- coding: utf-8 -*-

"""upload an apk"""

import ConfigParser
import argparse
import os
import sys
import re

from apiclient.discovery import build
import httplib2
from oauth2client import client
from oauth2client.service_account import ServiceAccountCredentials

config = ConfigParser.ConfigParser()
config.read('Config.ini')

AAPT_PATH = config.get('tool path', 'aapt_path')

JSON_KEY_FILE = config.get('key file', 'json_key')
P12_KEY_FILE = config.get('key file', 'p12_key')
P12_CLIENT_EMAIL = config.get('key file', 'p12_client_email')
P12_PRIVATE_KEY_PASSWORD = config.get('key file', 'p12_private_key_password')
scopes = ['https://www.googleapis.com/auth/androidpublisher']

# cmd arguments
argparser = argparse.ArgumentParser()
argparser.add_argument('apk_path',
                       help='The apk file path. Example: app-debug.apk')
argparser.add_argument('release_track',
                       help="The release track. Can be 'alpha', beta', 'production' or 'rollout'")
argparser.add_argument('-k', '--keytype', help="The key type. Can be 'json, 'p12'", default='json')


def main():
    # process arguments
    flags = argparser.parse_args()

    apk_path = flags.apk_path
    release_track = flags.release_track
    key_type = flags.keytype

    if 'json' == key_type:
        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            JSON_KEY_FILE, scopes=scopes)
    else:
        credentials = ServiceAccountCredentials.from_p12_keyfile(
            P12_CLIENT_EMAIL, P12_KEY_FILE, P12_PRIVATE_KEY_PASSWORD, scopes=scopes)
    http = httplib2.Http()
    http = credentials.authorize(http)

    service = build('androidpublisher', 'v2', http=http)
    
    print 'parsing input apk: %s' % apk_path

    # check apk info
    output = os.popen("%s d badging %s" % (AAPT_PATH, apk_path)).read()
    match = re.compile(
        "package: name='(\S+)' versionCode='(\d+)' versionName='(\S+)' platformBuildVersionName='\S+'").match(output)
    if not match:
        raise Exception("Cannot get apk info!!")
    package_name = match.group(1)
    version_code = match.group(2)
    version_name = match.group(3)

    print 'Package name: %s, versionName: %s, versionCode: %s' % (package_name, version_name, version_code)
    print 'Release track: %s' % release_track

    try:
        edit_request = service.edits().insert(body={}, packageName=package_name)
        result = edit_request.execute()
        edit_id = result['id']

        print 'uploading apk %s:%s(%s)' % (package_name, version_code, apk_path)
        upload_response = service.edits().apks().upload(
            editId=edit_id,
            packageName=package_name,
            media_mime_type='application/octet-stream',
            media_body=apk_path).execute()

        print 'result:'
        print upload_response

        track_response = service.edits().tracks().update(
            editId=edit_id,
            track=release_track,
            packageName=package_name,
            body={u'versionCodes': [upload_response['versionCode']]}).execute()

        print 'track %s is set for version code(s) %s' % (
            track_response['track'], str(track_response['versionCodes']))

        commit_request = service.edits().commit(
            editId=edit_id, packageName=package_name).execute()

        print 'Edit "%s" has been committed' % (commit_request['id'])
    except client.AccessTokenRefreshError:
        print('The credentials have been revoked or expired, please re-run the '
              'application to re-authorize')

if __name__ == '__main__':
    main()
