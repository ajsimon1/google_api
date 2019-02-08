'''
The core module houses the main functions for the api and interacts
with the cli module for proper functionality
'''
import base64
import datetime as dt
import os
import sys

from googleapiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

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
# grab base directory of script for relative file transfers
basedir = os.path.abspath(os.path.dirname(__file__))
# dump directory for attachments
attachdir = basedir+'//attachments//'
tradedata_tokens_f = 'td_tokens.json'
tradedata_credentials_f = 'client_id.json'
simon_tokens_f = 'as_tokens.json'
simon_credntials_f = 'credentials.json'
drive_credentials_f = 'drive_credentials.json'
drive_tokens_f = 'drive_tokens.json'

# function to validate credntial or tokens file and return build object
# note that gmail and v1 are hard coded in the build() method, should other
# google apis be needed, these values will need to parameterized
# added 'service' arg to genericize function and allow for multiple
# apis to use the same auth func
def authenticate(scopes, basedir, tokens_f, credentials_f, service, serv_vers):
    # start by creating a Storage() object to manage authorization
    # this is pulled from oauth2client lib file module.  the tokens.json
    # filename is passed as this is used for reoccuring authorized access to
    # the api.  if the tokens.json file is not available, the .get() method
    # will return none and the if statement will trigger the flow logic
    # to run.  This will in turn create a tokens.json file based on
    # downloaded credentials.json file
    store = file.Storage(os.path.join(basedir,tokens_f))
    # get() method on Storage object retrieves credentials from tokens.json
    # file, if that file does not exist var calling get() method will be empty
    creds = store.get()
    # logic statement checks to see if creds var was able to pull data from
    # tokens.json file.  If not, or if creds pulled are invalid, the
    # flow statement runs which creates a tokens.json file
    if not creds or creds.invalid:
        # since no tokens.json file is available or the data pulled from the
        # file is not valid, a flow object is created from client modules,
        # passing in credentials.json file and scopes.  credntials.json file
        # is downloaded from google API console and should be saved within
        # same namespace as script.  Also should be shared globally
        flow = client.flow_from_clientsecrets(os.path.join(basedir,
                                                          credentials_f),
                                                           scopes)
        # run_flow() method from tools module generates tokens.json file within
        # namespace and saved approriate data to creds var
        # note: when run for the first time, run_flow() will open a browser
        # tab to have user authorize application.  this is only done for initial
        # attempt to access gmail api, or is tokens.json data becomes invalid
        # the credentials.json file can be modified to update where the user
        # redirected if this authorization fails
        creds = tools.run_flow(flow, store)
    # build() func creates the interface between the client and api, utilizing
    # multiple class methods to pull specific resources from the provided api
    # list of supported apis at:
    # https://developers.google.com/api-client-library/python/apis/
    service = build(str(service), str(serv_vers), http=creds.authorize(Http()))
    # once service ojb created, chain methods together to pull down desired
    # resource.  various resources/collections available at:
    # https://developers.google.com/gmail/api/v1/reference/
    # note that different collections will have different required parameters
    # to pass.  of note is the 'q' parameter on messages().get(q='') which
    # allows to filter message list with same syntax used to search in gmail app
    # note the use of 'me' arg as userId, this is syntatic sugar to reference
    # current user, otherwise full email addr can be used
    # execute() method must be called
    return service

def pull_mail_from_query(build_obj, search_query):
    results = service.users().messages().list(userId='me',
                                              q=search_query).execute()
    # return object is dict, inside 'messages' key is a list of message
    # resources confirm messages were returned based on quesry filtering for
    # only messages with attachments
    if not results['messages']:
        print('No messages that match query: {}'.format(search_query))
    else:
        return results


def pull_attachs_from_query_results(results):
    messages = results['messages']
    # list var to to append message info tuples of
    # (attachmentId, messageId, filename). the script will iterate through this
    # list and call attachment.get() api on each attachmentId
    attach_ids = []
    # iterate through nested message list, wrapping in try block in case
    # message resource missing 'payload' or 'parts' key
    # TODO make try bloack/error messsaging more robust
    try:
        # iterate through messages list
        for message in messages:
            # call messages.get() to retrieve details on each message
            # including filename and attachmentId which is necessary to
            # pull actual attachment
            mess = service.users().messages().get(userId='me',
                                                 id=message['id']).execute()
            # variabilize messageId and message headers
            # while in the message object, headers include to, from, subject
            # information, both are added to info tuple for later processing
            m_id = mess['id']
            # NOT CORRECT m_headers = mess['payload']['headers']
            # iterate through parts in payload dict, if the file extension
            # for the filename in the message resource is in the accepted
            # list, append approriate info
            for part in mess['payload']['parts']:
                if part['filename'].split('.')[-1] in EXTENSIONS:
                    attach_ids.append((part['body']['attachmentId'],
                                        m_id,
                                        part['filename'],))
    # keyError exception accounts for any of the above keys being missing
    # while still allowing other errors to raise exception
    except KeyError:
        print('Passing on message id {}, no payload'.format(m_id))
    return attach_ids

def download_attachs(attach_ids_list, attachdir):
    # dict that will hold the actual attachments with attachmentId as the key
    attachments = {}
    # iterate the info tuples, extract the attachmentId, call attchments.get()
    # method to pull down the actual attachment, and add to dict, using the
    # filename as the key and the attachment data as the value
    for a_id in attach_ids_list:
            attachments[a_id[2]] = service.users()                             \
                                          .messages()                          \
                                          .attachments()                       \
                                          .get(userId='me',
                                               id=a_id[0],
                                               messageId=a_id[1]).execute()
    # iterate through the attachs dict, pulling fielname and file data with
    # items() call
    for k, v in attachments.items():
        # decode the byte code and variabilize as file_data, UTF-8 encoded
        file_data = base64.urlsafe_b64decode(v['data'].encode('UTF-8'))
        # open file with filepath as original filename and attachs dir, making
        # sure to open with 'wb' argument to ensure bytes are translated
        with open(attachdir+k, 'wb') as f:
            # write file_data and save
            f.write(file_data)
            f.close()
    return attachments, a_id

def batch_modify_message_label(attach_ids_list, label='Processing'):
    # pull down all available labels
    response = service.users().labels().list(userId='me').execute()
    # extract only labels list from entire response object
    labels = response['labels']
    # extrac label id from label id list, save in var
    proc_label_id = [val['id'] for val in labels if val['name']==label]
    # extract just the message ids to iclude as list in batchModify() method
    mess_ids = [a_id[1] for a_id in attach_ids_list]
    # ping api, if successful there is no return response for this
    batch_modify_body = {'ids': mess_ids,
                         'addLabelIds': proc_label_id,
                         'removeLabelIds': ['INBOX']}
    # wrapping in try clause in case label provided not available, then
    # catch IndexError and print message
    try:
        service.users()                                                        \
               .messages()                                                     \
               .batchModify(userId='me',body=batch_modify_body)                \
               .execute()
    except IndexError:
        print('{} label not found in user\'s inbox'.format(label))

def download_files_from_drive(service, fname, file_id=''):
    # check if file_id was passed to func; if not, retrieve file by filename
    if not file_id:
        # pull last 10 files chronologically, only provide id and name in
        # result set
        results = service.files()                                              \
                         .list(pageSize=10, fields='nextPageToken, files(id, name)')
                         .execute()
        # pull file content from metadata
        files = results.get('files', [])
        # check if return value was empty, if not iterate through and grab
        # the file id that matches the fname passed to the fucntion, save
        if not files:
            print('No files found.')
        else:
            for item in items:
                if item['name'].lower() == fname.lower():
                    file_id = item['id']
                else:
                    continue
    # grab the content of the file_id provided, return as plain text
    # NOTE: other mime type can be provided
    content = service.files()                                                  \
                     .export(fileId=file_id, mimeType='plain/text')            \
                     .execute()
    # save file in local directory using filename passed
    # TODO add path to fname for output dir, include this as a param of func
    with open(fname, 'wb') as f:
        f.write(content)
        f.close()
    return '{} downloaded from drive'.format(fname)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # search query can be added as an argument when calling the file
        search_query = sys.argv[1]
    else:
        # grab yesterday's date to use in gmail search query
        start_date = dt.datetime.now() - dt.timedelta(days=1)
        # search query to pull only emails with attachments received after
        # yesterday, additional query operators are located here:
        # https://support.google.com/mail/answer/7190?hl=en
        search_query = 'has:attachment after:{}'.format(start_date.strftime('%Y/%m/%d'))
    service = authenticate(scopes=SCOPES,
                           basedir=basedir,
                           tokens_f=tradedata_tokens_f,
                           credentials_f=tradedata_credentials_f,
                           service='gmail', # TODO pass these as argvs
                           serv_vers='v1') # TODO pass this as argvs
    results = pull_mail_from_query(service, search_query)
    attach_ids_list = pull_attachs_from_query_results(results=results)
    download_attachs(attach_ids_list=attach_ids_list, attachdir = attachdir)
    batch_modify_message_label(attach_ids_list, label='TESTING_GMAIL_API')