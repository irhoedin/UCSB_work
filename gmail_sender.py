from __future__ import print_function
import httplib2
import os

import apiclient
from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools

import base64
from email.mime.text import MIMEText
from email.utils import formatdate
import traceback


try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None


# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/gmail-python-quickstart.json

SCOPES = 'https://www.googleapis.com/auth/gmail.send'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = '<application_name>'

MAIL_FROM = "irhoedin@gmail.com"
MAIL_TO = "nori@mrl.ucsb.edu"

def get_credentials():

    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'gmail-send-api.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def create_message(receiver,subject,mail_str):
    message = MIMEText(mail_str)
    message["from"] = MAIL_FROM
    message["to"] = receiver
    message["subject"] = subject
    message["Date"] = formatdate(localtime=True)

    byte_msg = message.as_string().encode(encoding="UTF-8")
    byte_msg_b64encoded = base64.urlsafe_b64encode(byte_msg)
    str_msg_b64encoded = byte_msg_b64encoded.decode(encoding="UTF-8")

    return {"raw": str_msg_b64encoded}

def send_mail(receiver,subject,mail_str):

    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    try:
        result = service.users().messages().send(
            userId = MAIL_FROM,
            body=create_message(receiver,subject,mail_str)
        ).execute()

        print("Message Id: {}" .format(result["id"]))

    except apiclient.errors.HttpError:
        print("-----start trace-----")
        traceback.print_exc()
        print("-----end trace-----")


if __name__ == '__main__':
    send_mail("nori@mrl.ucsb.edu", 'test', "This is a test email from python gmail handlar")
