'''
The core module houses the main functions for the api and interacts
with the cli module for proper functionality
'''
import base64
import datetime as dt
import json
import os
import pickle
import sys

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

EXTENSIONS = ['txt', 'csv', 'xlsx', 'xls', '', 'dat', 'zip', 'rpg']

# function to authenticate app with previoulsy built token file or credentials
# file downloaded for google api console
# returns service object used to communicate with api
def authenticate(scopes, basedir, credentials_f, service, serv_vers):
    # set creds to None to allow unpickled tokens to populate empty var
    creds = None
    # check if token.pickle file exists in basedir var passed
    # if yes, this file is used to authenticate service
    if service == 'gmail':
        pickle_f = 'td_gmail_token.pickle'
    elif service == 'drive' or service == 'sheets':
        pickle_f = 'pers_drive_token.pickle'

    full_token_path = os.path.join(basedir,pickle_f)
    full_creds_path = os.path.join(basedir,credentials_f)
    if os.path.exists(full_token_path):
        with open(full_token_path, 'rb') as token:
            creds = pickle.load(token)
    # if token.pcikle does not exist or if creds is invalid, then use passed
    # credentials file to create new token.pickle or refresh old token file
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # use provided credntials file with defined scopes to generate
            # token file
            flow = InstalledAppFlow.from_client_secrets_file(full_creds_path,
                                                             scopes)
            creds = flow.run_local_server()
            # create new token.pickle
            with open(full_token_path, 'wb') as token:
                pickle.dump(creds,token)
    # create service object to return, based on google service and version
    # provided
    service = build(str(service), str(serv_vers), credentials=creds)
    return service

def pull_mail_from_query(build_obj, search_query):
    results = build_obj.users().messages().list(userId='me',
                                                labelsIds=['Inbox'],
                                                q=search_query).execute()
    # return object is dict, inside 'messages' key is a list of message
    # resources confirm messages were returned based on quesry filtering for
    # only messages with attachments
    if not results['messages']:
        print('No messages that match query: {}'.format(search_query))
    else:
        return results


def pull_attachs_from_query_results(build_obj, results):
    messages = results['messages']
    # list var to to append message info tuples of
    # (attachmentId, messageId, filename). the script will iterate through this
    # list and call attachment.get() api on each attachmentId
    attach_ids = []
    # iterate through nested message list, wrapping in try block in case
    # message resource missing 'payload' or 'parts' key
    # TODO make try bloack/error messsaging more robust
        # iterate through messages list
    for message in messages:
        # call messages.get() to retrieve details on each message
        # including filename and attachmentId which is necessary to
        # pull actual attachment
        mess = build_obj.users().messages().get(userId='me',
                                             id=message['id']).execute()
        # variabilize messageId and message headers
        # while in the message object, headers include to, from, subject
        # information, both are added to info tuple for later processing
        m_id = mess['id']
        # grab from email addr from message
        from_addr = grab_from_addr(m_id, build_obj)
        # NOT CORRECT m_headers = mess['payload']['headers']
        # iterate through parts in payload dict, if the file extension
        # for the filename in the message resource is in the accepted
        # list, append approriate info
        try:
            for part in mess['payload']['parts']:
                if part['filename']:
                    if part['filename'].split('.')[-1].lower() in EXTENSIONS:
                        attach_ids.append((part['body']['attachmentId'],
                                            m_id,
                                            from_addr,
                                            part['filename'],))
                    else:
                        print('File extension for message id {}, not accetpable '\
                            'extension'.format(m_id))
                        continue
                else:
                    continue
        except KeyError:
            try:
                if mess['payload']['filename']:
                    if mess['payload']['filename'].split('.')[-1].lower() in EXTENSIONS:
                        attach_ids.append((mess['payload']['body']['attachmentId'],
                                            m_id,
                                            from_addr,
                                            mess['payload']['filename'],))
                    else:
                        print('File extension for message id {}, not accetpable '\
                            'extension'.format(m_id))
                        continue
                else:
                    continue
            except KeyError:
                print('Message {} has no payload'.format(m_id))

    # keyError exception accounts for any of the above keys being missing
    # while still allowing other errors to raise exception
    return attach_ids

def download_attachs(build_obj, attach_ids_list, attachdir):
    # dict that will hold the actual attachments with attachmentId as the key
    attachments = {}
    # iterate the info tuples, extract the attachmentId, call attchments.get()
    # method to pull down the actual attachment, and add to dict, using the
    # filename as the key and the attachment data as the value
    for a_id in attach_ids_list:
            attachments[a_id[3]] = build_obj.users()                           \
                                            .messages()                        \
                                            .attachments()                     \
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
    return attachments

def batch_modify_message_label(build_obj, attach_ids_list, label='Processing'):
    # pull down all available labels
    response = build_obj.users().labels().list(userId='me').execute()
    # extract only labels list from entire response object
    labels = response['labels']
    # extrac label id from label id list, save in var
    proc_label_id = [val['id'] for val in labels if val['name']==label]
    # extract just the message ids to iclude as list in batchModify() method
    mess_ids = [a_id[1] for a_id in attach_ids_list]
    # ping api, if successful there is no return response for this
    batch_modify_body = {'ids': mess_ids,
                         'addLabelIds': proc_label_id,
                         'removeLabelIds': ['Inbox']}
    # wrapping in try clause in case label provided not available, then
    # catch IndexError and print message
    try:
        build_obj.users()                                                      \
                 .messages()                                                   \
                 .batchModify(userId='me',body=batch_modify_body)              \
                 .execute()
    except IndexError:
        print('{} label not found in user\'s inbox'.format(label))
    return None

def download_files_from_drive(service, fname, file_id='', out_dir=''):
    # check if file_id was passed to func; if not, retrieve file by filename
    if not file_id:
        # pull last 10 files chronologically, only provide id and name in
        # result set
        # TODO add option to limit # of files with pageSize arg
        results = service.files()                                              \
                         .list(fields='nextPageToken, files(id, name)')        \
                         .execute()
        # pull file content from metadata
        files = results.get('files', [])
        # check if return value was empty, if not iterate through and grab
        # the file id that matches the fname passed to the fucntion, save
        if not files:
            print('No files found.')
        else:
            for item in files:
                if item['name'].lower() == fname.lower():
                    file_id = item['id']
                else:
                    continue
    # grab the content of the file_id provided, return as plain text
    # NOTE: other mime type can be provided
    content = service.files()                                                  \
                     .export(fileId=file_id, mimeType='text/csv')              \
                     .execute()
    # save file in local directory using filename passed
    # TODO add path to fname for output dir, include this as a param of func
    save_fname = fname+'.csv'
    if out_dir:
        save_fname = os.path.join(out_dir, save_fname)
    with open(save_fname, 'wb') as f:
        f.write(content)
        f.close()
    return '{} downloaded from drive'.format(save_fname)

def grab_from_addr(mess_ids, build_obj, lst=False):
    from_addr_dict = {}
    if lst:
        for mess_id in mess_ids:
            mess = build_obj.users()                                           \
                            .messages()                                        \
                            .get(userId='me', id=mess_id)                      \
                            .execute()
            for sect in mess['payload']['headers']:
                if sect['name'] == 'From':
                    from_addr_dict[mess_id] = sect['value']
                    break
                else:
                    from_addr_dict[mess_id] = 'NULL'
        return from_addr_dict
    else:
        mess = build_obj.users()                                               \
                        .messages()                                            \
                        .get(userId='me', id=mess_ids)                         \
                        .execute()
        for sect in mess['payload']['headers']:
            if sect['name'] == 'From':
                return sect['value']
            else:
                continue

def query_sheets(build_obj, sheet_id, ranges):
    # sample ranges = [Sheet1!A1:B35]
    query_results = build_obj.spreadsheets()                                   \
                             .get(spreadsheetId=sheet_id,
                                  ranges=ranges,
                                  includeGridData=True)                        \
                             .execute()
    response_lst = [[j['formattedValue'] for j in i['values']]
                    for i
                    in query_results['sheets'][0]['data'][0]['rowData']]

    return response_lst

def build_json(file_details, look_up_file, output_dir):
    output_dict = {}
    create_date = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_filename = '{0}_c2b_trade_date_email_output.json'.format(create_date)
    output_dict['create_date'] = create_date
    output_dict['files_downloaded'] = len(file_details)
    output_dict['file_details'] = {}
    file_count = 0
    # details_tup contains, attach id, mess id, from addr, filename in that
    for item in file_details:
        output_dict['file_details'][file_count] = {
            'attachment_id': item[0],
            'message_id': item[1],
            'from_email_dom': item[2].split('@')[-1].split('.')[0],
            'filename': item[1] + '_' + item[3]
        }
        file_count += 1
    for file_detail in output_dict['file_details'].values():
        for look_up_file_item in look_up_file:
            if file_detail['from_email_dom'] in look_up_file_item:
                file_detail['folder_name'] = look_up_file_item[1]
                file_detail['provider_id'] = look_up_file_item[2]
                file_detail['email_from_domain'] = look_up_file_item[0]
    output = json.dumps(file_dict)
    with open(output_dir+out_filename, 'w') as f:
        f.write(output)
        f.close()
    return None
