'''
The cli module interacts with the user via the comman line module through
the argparse
'''
import argparse
import datetime as dt
import os

import google_api_core as gac

parser = argparse.ArgumentParser(description='CLI wrapper for google services' \
                                             ' api')
parser.add_argument('service', help='specify the google service to connect to,'\
                                    ' [drive, gmail]')
parser.add_argument('-q', '--query', type=str, help='Pass query to service')
parser.add_argument('-n', '--name', type=str, help='Pass name of resource to ' \
                                                'service')
parser.add_argument('-o', '--out', help='Path of desired output directory')
parser.add_argument('-c', '--credentials', help='specify credentials file to ' \
                                            'use')
parser.add_argument('-d',
                    '--query_date',
                    type=int,
                    help='days from current date to include in query. e.g. '   \
                    'if looking for all mail from yesterday, pass 1; if 2 days'\
                    'back pass 2, etc.')
parser.add_argument('-s', '--sheet_id', help='sheet ID to query')
parser.add_argument('-r','--ranges', help='ranges to query on sheet')


# grab base directory of script for relative file transfers
# can use os.getcwd() if __file__ not available
basedir = os.path.abspath(os.path.join(__file__,'../..'))
# dump directory for attachments
attachdir = basedir+'\\attachments\\'
personal_credentials_f = os.path.abspath(os.path.join(basedir,'drive_sheets_credentials.json'))
tradedata_credentials_f = os.path.abspath(os.path.join(basedir,'client_secret_c2b_gmail.json'))

# scope necessary is for gmail readonly, a list of scopes can be found at
# https://developers.google.com/gmail/api/auth/scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.readonly',
          'https://www.googleapis.com/auth/spreadsheets.readonly']

# validate attachments against 'accepted' list to only pull down certain files
# TODO files with alternate extensions should not be discarded but dumped into
# separate bucket
EXTENSIONS = ['txt', 'csv', 'xlsx', 'xls', '', 'dat', 'zip', 'rpg', 'acf']

# set dict to manage current versions of each service
up_to_date_service_versions = {
    'drive': 'v3',
    'gmail': 'v1',
    'sheets': 'v4',
}

def run(args):
    if args.credentials == 'tradedata':
        credentials_f = tradedata_credentials_f
    elif args.credentials == 'personal':
        credentials_f = personal_credentials_f
    serv_vers = up_to_date_service_versions[args.service]
    service = gac.authenticate(scopes=SCOPES,
                               basedir=basedir,
                               credentials_f=credentials_f,
                               service = args.service,
                               serv_vers=serv_vers)
    if args.service == 'drive':
        gac.download_files_from_drive(service, args.name, out_dir=args.out)
    elif args.service == 'gmail':
        if args.query_date:
            query_date = args.query_date
        else:
            query_date = 1
        if args.sheet_id:
            sheets_service = gac.authenticate(scopes=SCOPES,
                                              basedir=basedir,
                                              credentials_f=personal_credentials_f,
                                              service='sheets',
                                              serv_vers='v4')
            look_up_details = gac.query_sheets(sheets_service,
                                               sheet_id = args.sheet_id,
                                               ranges = args.ranges)
        start_date = dt.datetime.now() - dt.timedelta(days=args.query_date)
        search_query = args.query + ' after:{}'.format(start_date.strftime('%Y/%m/%d'))
        results = gac.pull_mail_from_query(service, search_query)
        if type(results) == str:
            gac.build_json(args.out, error_mess=results)
            return None
        # details_tup contains, attach id, mess id, from addr, filename in that
        # order
        file_details_tup, not_accepted = gac.pull_attachs_from_query_results(build_obj=service,
                                                                             results=results)
        # attach_dict contains filename as key and base64 encoded data as value
        attach_dict = gac.download_attachs(build_obj=service,
                                           attach_ids_list=file_details_tup,
                                           attachdir = attachdir)
        sheets_data = gac.query_sheets(build_obj=sheets_service,
                                       sheet_id=args.sheet_id,
                                       ranges=args.ranges)
        not_found_mess_ids = gac.build_json(output_dir=args.out,
                                            not_accepted_tup=not_accepted,
                                            file_details=file_details_tup,
                                            look_up_file=sheets_data,)
        gac.batch_modify_message_label(build_obj=service,
                                       attach_ids_list=file_details_tup,
                                       not_found_lst=not_found_mess_ids,
                                       label='Automation_Processed',)
    return None

if __name__ == '__main__':
    args = parser.parse_args()
    run(args)
