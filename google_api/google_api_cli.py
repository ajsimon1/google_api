'''
Author: Adam Simon
Created: 02/01/19
Updated: 03/19/19
Github: https://github.com/ajsimon1/google_api.git
The cli module interacts with the user via the comman line module through
the argparse

Notes: User should note this app uses OAuth 2.0 and requires user approval via
       we browser the first time the app runs based on credentials downloaded
       from google api console; after approval a pickle file is created in
       local directort for future uses without the need for browser approval;
       it's suggested that user run script locally with credentials than save
       pickle in remote directory to run
'''
import argparse
import datetime as dt
import os

import google_api_core as gac

################################################################################
# ############################ SET CLI ARGS ################################## #
################################################################################
parser = argparse.ArgumentParser(description='CLI wrapper for google services' \
                                             ' api')

# required arg to determine which service is being used, expceted in first
# position after filename
parser.add_argument('service', help='specify the google service to connect to,'\
                                    ' [drive, gmail]')

# query to send service, only applicable for certain services, in this case
# used as a gmail query against an inbox
parser.add_argument('-q', '--query', type=str, help='Pass query to service')

# name of resource to search for, in this case name of google sheets resource
parser.add_argument('-n', '--name', type=str, help='Pass name of resource to ' \
                                                'service')

# output directory to drop anything being returned by api
parser.add_argument('-o', '--out', help='Path of desired output directory')

# filename for credentials downloaded from google api console, see notes above
parser.add_argument('-c', '--credentials', help='specify credentials file to ' \
                                            'use')

# date to add to query, ie days minus today that should be included in range
parser.add_argument('-d',
                    '--query_date',
                    type=int,
                    help='days from current date to include in query. e.g. '   \
                    'if looking for all mail from yesterday, pass 1; if 2 days'\
                    'back pass 2, etc.')

# sheet id for sheets api, can be pulled from URL while sheet is open in browser
parser.add_argument('-s', '--sheet_id', help='sheet ID to query')

# ranges to pass to sheet api; format is Sheet1!A1:F100
parser.add_argument('-r','--ranges', help='ranges to query on sheet')

# directory to drop attachments pulled from gmail api
parser.add_argument('-a', '--attach_dir', help='specify dir for attachments '  \
                          'to download to, otherwise, uses parent dir of file')
# boolean to make directories if output doesn't exist or to raise exception
parser.add_argument('-m', '--mkdir', type=bool, help='create output dir and '  \
                    'parents if it doesn\'t already exist or raise exception')

################################################################################
# ############################ SET VARIABLES ################################# #
################################################################################

# grab base directory of script for relative file transfers
# can use os.getcwd() if __file__ not available
basedir = os.path.abspath(os.path.join(__file__,'../..'))

# default dump directory for attachments, if not passed in CLI
attachdir = basedir+'\\attachments\\'

# path for credntials fil, as stated in notes above, user should be creating
# pickle files locally based on these credentials and saving the pickle file
# in the remtoe directory where the script will execute
personal_credentials_f = os.path.abspath(os.path.join(basedir,'drive_sheets_'  \
                                                            'credentials.json'))
tradedata_credentials_f = os.path.abspath(os.path.join(basedir,'client_secret_'\
                                                              'c2b_gmail.json'))

# a list of scopes for app to execute against, complete list found at:
# https://developers.google.com/gmail/api/auth/scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/spreadsheets.readonly']

# list of acceptable file extensions, files with extensions not on the list
# are passed and left in the inbox
EXTENSIONS = ['txt', 'csv', 'xlsx', 'xls', '', 'dat', 'zip', 'rpg', 'acf']

# google api requires service version to be passed during build function
up_to_date_service_versions = {
    'drive': 'v3',
    'gmail': 'v1',
    'sheets': 'v4',
}

################################################################################
# ############################ MAIN FUNCTION ################################# #
################################################################################
def run(args):
    # set path for credentials using specific filename based on credentials arg
    # passed in CLI; app should only be using pickle files in prod
    if args.credentials == 'tradedata':
        credentials_f = tradedata_credentials_f
    elif args.credentials == 'personal':
        credentials_f = personal_credentials_f
    # grab current version from dict above
    serv_vers = up_to_date_service_versions[args.service]
    # returns service object used for specific api methods
    service = gac.authenticate(scopes=SCOPES,
                               basedir=basedir,
                               credentials_f=credentials_f,
                               service = args.service,
                               serv_vers=serv_vers)
    # currently only 1 workflow for drive service
    if args.service == 'drive':
        gac.download_files_from_drive(service, args.name, out_dir=args.out)
    # workflow for gmail api to pull down attachments, a portion of this
    # workflow uses the sheets api which currently hardcoded to use personal
    # credentials while the gmail service uses tradedata credentials
    elif args.service == 'gmail':
        # query date sets the range to today that should be searched againt the
        # inbox, ie value of 4 = search for all emails from 4 days ago to today
        if args.query_date:
            query_date = args.query_date
        else:
            # default query date is 1, can probably set this in argparse
            query_date = 1
        # workflow for sheets api call, as mentioned above; this workflow is
        # currently hardcoded
        if args.sheet_id:
            sheets_service = gac.authenticate(scopes=SCOPES,
                                              basedir=basedir,
                                              credentials_f=personal_credentials_f,
                                              service='sheets',
                                              serv_vers='v4')
            look_up_details = gac.query_sheets(sheets_service,
                                               sheet_id = args.sheet_id,
                                               ranges = args.ranges)
        # set start of query as today minus query date passed in CLI
        start_date = dt.datetime.now() - dt.timedelta(days=query_date)
        # format date in gmail query approriately, see URL for more options:
        # https://support.google.com/mail/answer/7190?hl=en
        search_query = args.query + ' after:{}'.format(start_date.strftime('%Y/%m/%d'))
        # results of search query returned as a dict if there were no issues
        results = gac.pull_mail_from_query(service, search_query)
        # results returns as string if there was an issue, ie the inbox was
        # empty or or there were no attachments within the specific date range
        # json file is still created with query passed in CLI
        if type(results) == str:
            gac.build_json(args.out, error_mess=results)
            return None
        # details_tup contains, attach id, mess id, from addr, filename in that
        # order; not accepted contains any messages that had file extensions
        # not in the accepted extensions list
        file_details_tup, not_accepted = gac.pull_attachs_from_query_results(build_obj=service,
                                                                             results=results)
        # sheets data is values in cells in range in sheet passed to CLI
        sheets_data = gac.query_sheets(build_obj=sheets_service,
                                       sheet_id=args.sheet_id,
                                       ranges=args.ranges)
        # attach_dict contains filename as key and base64 encoded data as value
        if args.attach_dir:
            attachdir = args.attach_dir
        # attach dict contains filename prepended with foldername as key, with
        # values as attach_id, message_id, foldername, providerid
        attach_dict = gac.download_attachs(build_obj=service,
                                           attach_ids_list=file_details_tup,
                                           attachdir=attachdir,
                                           look_up_file=sheets_data,
                                           mkdir=args.mkdir)
        # not found messages is passed to batch_modify function to ensure
        # that any messages that did not have corresponding folder name are not
        # marked as read and pushed out of inbox
        not_found_mess_ids = gac.build_json(output_dir=args.out,
                                            not_accepted_tup=not_accepted,
                                            file_details=file_details_tup,
                                            look_up_file=sheets_data,)
        # update labels on emails to passed label, removing inbox as a label
        # and marking the emails as read, the
        gac.batch_modify_message_label(build_obj=service,
                                       attach_ids_list=file_details_tup,
                                       not_found_lst=not_found_mess_ids,
                                       label='Automation_Processed',)
    return None

if __name__ == '__main__':
    args = parser.parse_args()
    run(args)
