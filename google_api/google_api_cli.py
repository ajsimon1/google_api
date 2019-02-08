'''
The cli module interacts with the user via the comman line module through
the argparse
'''
import argparse
import os

from . import google_api_core as gac

parser = argparse.ArgumentParser(description='CLI wrapper for google services' \
                                             ' api')
parser.add_argument('service', help='specify the google service to connect to,'\
                                    ' [drive, gmail]')
parser.add_argument('authenticate', help='Function authenticates user with '    \
                                        'google account.  This may require '   \
                                        'authorization')
parser.add_argument('-q --query', type=str, help='Pass query to service')
parser.add_argument('-n --mame', type=str, help='Pass name of resource to '     \
                                               'service')

# TODO figure out best options/arguments
# having a positional arg for which google service is being called might be
# beneficial, python google_api drive or python google_api gmail
# defaults should be credentials files
# optional argument

# grab base directory of script for relative file transfers
# can use os.getcwd() if __file__ not available
basedir = os.path.abspath(os.path.dirname(__file__))
# dump directory for attachments
attachdir = basedir+'..//attachments//'
drive_credentials_f = 'drive_credentials.json'
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
EXTENSIONS = ['txt', 'csv', 'xlsx', 'xls']

up_to_date_service_versions = {
    'drive': 'v3',
    'gmail': 'v1'
}

def run(args):
    serv_vers = up_to_date_service_versions[args.service]
    service = gac.authenticate(scopes=SCOPES,
                               basedir=basedir,
                               tokens_f=drive_tokens_f,
                               credentials_f=drive_credentials_f,
                               service = args.service,
                               serv_vers=serv_vers)
    gac.download_files_from_drive(service, fname)
    return None

if __name__ == '__main__':
    args = parser.parse_args()

    run(args)
