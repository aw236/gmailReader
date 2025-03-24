import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email import policy
from email.parser import BytesParser
import html2text

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


def get_threads_involving_user(service, user_email, max_results=1000):
    """Fetch threads involving a specific user."""
    try:
        # Search for threads involving the specified user
        query = f'{user_email}'
        page_token = None
        all_threads = []
        while True:
            results = service.users().threads().list(userId='me', q=query, maxResults=max_results,
                                                     pageToken=page_token).execute()
            threads = results.get('threads', [])
            all_threads.extend(threads)
            page_token = results.get('nextPageToken')
            if not page_token:
                break
        return all_threads
    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def get_emails_in_thread(service, thread_id):
    """Fetch all emails in a thread and return metadata and plaintext content."""
    try:
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        messages = thread.get('messages', [])

        email_data = []
        for msg in messages:
            # Extract subject, date, and sender from headers
            headers = msg['payload']['headers']
            subject = next((header['value'] for header in headers if header['name'].lower() == 'subject'), 'No Subject')
            date = next((header['value'] for header in headers if header['name'].lower() == 'date'), 'No Date')
            sender = next((header['value'] for header in headers if header['name'].lower() == 'from'), 'Unknown Sender')

            # Get the raw message for plaintext extraction
            raw_msg = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
            msg_data = base64.urlsafe_b64decode(raw_msg['raw'].encode('ASCII'))
            msg_parsed = BytesParser(policy=policy.default).parsebytes(msg_data)

            # Try to get the plaintext part
            plaintext_part = msg_parsed.get_body(preferencelist=('plain'))
            if plaintext_part:
                body = plaintext_part.get_content().strip()
            else:
                # Fall back to HTML part if plaintext is not available
                html_part = msg_parsed.get_body(preferencelist=('html'))
                if html_part:
                    html_content = html_part.get_content().strip()
                    # Convert HTML to plaintext
                    h = html2text.HTML2Text()
                    h.ignore_links = False  # Keep links in the text
                    body = h.handle(html_content).strip()
                else:
                    body = "No plaintext or HTML content found."

            # Store the email data
            email_data.append({
                'subject': subject,
                'date': date,
                'sender': sender,
                'body': body
            })

        return email_data

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def save_to_file(email_data, filename='emails.txt'):
    """Save the email metadata and plaintext to a file."""
    with open(filename, 'w', encoding='utf-8') as f:
        for i, email in enumerate(email_data, 1):
            f.write(f"Email {i}:\n")
            f.write(f"Subject: {email['subject']}\n")
            f.write(f"Date: {email['date']}\n")
            f.write(f"Sender: {email['sender']}\n")
            f.write(f"Body:\n{email['body']}\n")
            f.write(f"{'-' * 50}\n")


if __name__ == '__main__':
    # Replace with the email address of the sender you want to search for
    user_email = "premierpadsrentals@gmail.com"  # Replace with the actual email address
    service = get_gmail_service()

    # Get all threads involving the user
    threads = get_threads_involving_user(service, user_email, max_results=1000)

    if not threads:
        print(f"No threads found involving {user_email}.")
    else:
        all_emails = []
        for thread in threads:
            thread_emails = get_emails_in_thread(service, thread['id'])
            all_emails.extend(thread_emails)

        if all_emails:
            save_to_file(all_emails)
            print(f"Downloaded {len(all_emails)} emails and saved to 'emails.txt'.")
        else:
            print("No emails downloaded.")
