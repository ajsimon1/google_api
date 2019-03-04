'''
The cli module interacts with the user via the comman line module through
the argparse
'''
import argparse
import os

import google_api_core as gac

parser = argparse.ArgumentParser(description='CLI wrapper for google services' \
                                             ' api')
parser.add_argument('service', help='specify the google service to connect to,'\
                                    ' [drive, gmail]')
#parser.add_argument('authenticate', help='Function authenticates user with google account.  This may require authorization')
parser.add_argument('-q', '--query', type=str, help='Pass query to service')
parser.add_argument('-n', '--name', type=str, help='Pass name of resource to ' \
                                                'service')
parser.add_argument('-o', '--out', help='Path of desired output directory')
parser.add_argument('-c', '--credentials', help='specify credentials file to ')\
                                            'use')
parser.add_argument('-d',
                    '--querydate',
                    type=int,
                    help='days from current date to include in query. e.g. '   \
                    'if looking for all mail from yesterday, pass 1; if 2 days'\
                    'back pass 2, etc.'

# TODO figure out best options/arguments
# having a positional arg for which google service is being called might be
# beneficial, python google_api drive or python google_api gmail
# defaults should be credentials files
# optional argument

# grab base directory of script for relative file transfers
# can use os.getcwd() if __file__ not available
basedir = os.path.abspath(os.path.join(__file__,'../..'))
# dump directory for attachments
attachdir = basedir+'..//attachments//'
personal_credentials_f = 'drive_credentials.json'
tradedata_credentials_f = 'client_secret_c2b_gmail.json'
drive_tokens_f = 'drive_tokens.json'


# scope necessary is for gmail readonly, a list of scopes can be found at
# https://developers.google.com/gmail/api/auth/scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/drive.metadata.readonly',
          'https://www.googleapis.com/auth/drive.readonly']
# validate attachments against 'accepted' list to only pull down certain files
# TODO files with alternate extensions should not be discarded but dumped into
# separate bucket
EXTENSIONS = ['txt', 'csv', 'xlsx', 'xls', '', 'dat', 'zip', 'rpg']

# set dict to manage current versions of each service
up_to_date_service_versions = {
    'drive': 'v3',
    'gmail': 'v1'
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
        if args.querydate:
            query_date = args.querydate
        else:
            query_date = 1
        start_date = dt.datetime.now() - dt.timedelta(days=query_date)
        search_query = args.query + ' after {}'.format(start_date.strftime('%Y/%m/%d'))
        results = gac.pull_mail_from_query(service, search_query)
        # details_tup contains, attach id, mess id, from addr, filename in that
        # order
        details_tup = pull_attachs_from_query_results(build_obj=service,
                                                     results=results)
        # attach_dict contains filename as key and base64 encoded data as value
        attach_dict = download_attachs(build_obj=service,
                                       attach_ids_list=attach_ids_list,
                                       attachdir = attachdir)
        batch_modify_message_label(build_obj=service,
                                   attach_ids_list=attach_ids_list,
                                   label='Processed')

        # TODO add filename to attach_ids tuple


    return None

if __name__ == '__main__':
    args = parser.parse_args()
    run(args)
