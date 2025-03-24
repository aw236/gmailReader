import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email import policy
from email.parser import BytesParser

# Define the scopes (read-only access to Gmail)
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def get_gmail_service():
    """Authenticate and build the Gmail API service."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)


def get_emails_from_user(service, user_email, max_results=100):
    """Fetch emails from a specific user and return metadata and plaintext content."""
    try:
        # Search for emails from the specified user
        query = f'from:{user_email}'
        # Handle pagination to get all emails
        page_token = None
        all_messages = []
        while True:
            results = service.users().messages().list(userId='me', q=query, maxResults=max_results,
                                                      pageToken=page_token).execute()
            messages = results.get('messages', [])
            all_messages.extend(messages)
            page_token = results.get('nextPageToken')
            if not page_token:
                break

        email_data = []
        if not all_messages:
            print(f"No emails found from {user_email}.")
            return email_data

        for message in all_messages:
            # Get the full message with headers
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()

            # Extract subject and date from headers
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
            date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'No Date')

            # Get the raw message for plaintext extraction
            raw_msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
            msg_data = base64.urlsafe_b64decode(raw_msg['raw'].encode('ASCII'))
            msg_parsed = BytesParser(policy=policy.default).parsebytes(msg_data)
            plaintext_part = msg_parsed.get_body(preferencelist=('plain'))
            plaintext = plaintext_part.get_content().strip() if plaintext_part else "No plaintext content found."

            # Store the email data (subject, date, body)
            email_data.append({
                'subject': subject,
                'date': date,
                'body': plaintext
            })

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def save_to_file(email_data, user_email, filename='emails.txt'):
    """Save the email metadata and plaintext to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        for i, email in enumerate(email_data, 1):
            f.write(f"Email {i} from {user_email}:\n")
            f.write(f"Subject: {email['subject']}\n")
            f.write(f"Date: {email['date']}\n")
            f.write(f"Body:\n{email['body']}\n")
            f.write(f"{'-' * 50}\n")


if __name__ == '__main__':
    # Replace with the email address of the sender you want
    # user_email = "example.sender@gmail.com"  # Replace with the actual email address
    user_email = "asdf123@gmail.com"  # Replace with the email address of the sender you want # Downloaded 2 emails and saved to 'emails.txt'.
    service = get_gmail_service()
    emails = get_emails_from_user(service, user_email, max_results=1000)  # Adjust max_results as needed
    if emails:
        save_to_file(emails, user_email)
        print(f"Downloaded {len(emails)} emails and saved to 'emails.txt'.")
    else:
        print("No emails downloaded.")
